#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from client import CommandCenterClient  # noqa: E402

MANIFEST_PATHS = (
    Path(".command-center/architecture.yaml"),
    Path(".command-center/architecture.yml"),
    Path(".command-center/architecture.json"),
)
MAX_DOCUMENT_BYTES = 512 * 1024
MAX_DOCUMENT_COUNT = 1_000
MAX_CORPUS_BYTES = 20 * 1024 * 1024


def find_repository(start: Path) -> tuple[Path, Path]:
    current = start.expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        for relative in MANIFEST_PATHS:
            path = candidate / relative
            if path.is_file():
                return candidate, path
    raise FileNotFoundError(
        "No .command-center/architecture.yaml or .json manifest was found."
    )


def _load_manifest(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    if path.suffix.casefold() == ".json":
        parsed = json.loads(raw)
    else:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError(
                "YAML manifest support requires PyYAML. Use architecture.json "
                "or install the Command Center Python dependencies."
            ) from exc
        parsed = yaml.safe_load(raw)
    if not isinstance(parsed, dict):
        raise ValueError("architecture manifest must be a mapping")
    allowed = {"schema_version", "repository", "documents", "dialects"}
    unknown = set(parsed) - allowed
    if unknown:
        raise ValueError(
            "unknown architecture manifest fields: " + ", ".join(sorted(unknown))
        )
    if parsed.get("schema_version") != 1:
        raise ValueError("architecture manifest schema_version must be 1")
    repository = parsed.get("repository")
    rules = parsed.get("documents")
    if not isinstance(repository, dict) or not isinstance(rules, dict):
        raise ValueError("manifest requires repository and documents mappings")
    if set(repository) - {"id", "name", "aliases"}:
        raise ValueError("repository manifest contains unsupported fields")
    if set(rules) - {"roots", "patterns", "exclude"}:
        raise ValueError("documents manifest contains unsupported fields")
    repository_id = str(repository.get("id") or "")
    repository_name = str(repository.get("name") or "")
    if not repository_id or not repository_name:
        raise ValueError("repository id and name are required")
    return parsed, hashlib.sha256(raw).hexdigest()


def _relative(value: str, field: str) -> PurePosixPath:
    if not value or "\\" in value or "\x00" in value:
        raise ValueError(f"{field} must be a repository-relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field} must not traverse outside the repository")
    return path


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _revision(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip()[:160]


def inventory(start: Path) -> dict[str, Any]:
    root, manifest_path = find_repository(start)
    manifest, manifest_hash = _load_manifest(manifest_path)
    rules = manifest["documents"]
    roots = rules.get("roots") or []
    patterns = rules.get("patterns") or ["**/*.md"]
    excludes = rules.get("exclude") or []
    if not isinstance(roots, list) or not roots:
        raise ValueError("documents.roots must be a non-empty list")
    if not isinstance(patterns, list) or not isinstance(excludes, list):
        raise ValueError("document patterns and excludes must be lists")
    for value in [*roots, *patterns, *excludes]:
        _relative(str(value), "document path")

    selected: dict[str, Path] = {}
    root = root.resolve()
    for value in roots:
        relative = _relative(str(value), "document root")
        document_root = (root / Path(*relative.parts)).resolve()
        if not _inside(root, document_root):
            raise ValueError("document root escapes the repository")
        if not document_root.exists():
            continue
        for pattern in patterns:
            for path in document_root.glob(str(pattern)):
                if not path.is_file():
                    continue
                resolved = path.resolve()
                if not _inside(root, resolved):
                    raise ValueError("architecture document symlink escapes the repository")
                source_uri = resolved.relative_to(root).as_posix()
                if any(PurePosixPath(source_uri).match(str(item)) for item in excludes):
                    continue
                if resolved.suffix.casefold() != ".md":
                    raise ValueError("architecture sync accepts Markdown documents only")
                selected[source_uri] = resolved
    if not selected:
        raise ValueError("architecture manifest selected no documents")
    if len(selected) > MAX_DOCUMENT_COUNT:
        raise ValueError("architecture corpus contains too many documents")

    documents: list[dict[str, str]] = []
    hashes: list[dict[str, str]] = []
    total_bytes = 0
    for source_uri, path in sorted(selected.items()):
        raw = path.read_bytes()
        if len(raw) > MAX_DOCUMENT_BYTES:
            raise ValueError(f"architecture document is too large: {source_uri}")
        total_bytes += len(raw)
        if total_bytes > MAX_CORPUS_BYTES:
            raise ValueError("architecture corpus is too large")
        content = raw.decode("utf-8")
        content_hash = hashlib.sha256(raw).hexdigest()
        documents.append({"source_uri": source_uri, "content": content})
        hashes.append({"source_uri": source_uri, "content_hash": content_hash})
    return {
        "root": root,
        "manifest_path": manifest_path,
        "manifest": manifest,
        "manifest_hash": manifest_hash,
        "source_revision": _revision(root),
        "documents": documents,
        "hashes": hashes,
        "total_bytes": total_bytes,
    }


def _repository(payload: dict[str, Any]) -> dict[str, Any]:
    repository = payload["manifest"]["repository"]
    aliases = repository.get("aliases") or []
    if not isinstance(aliases, list):
        raise ValueError("repository.aliases must be a list")
    return {
        "id": str(repository["id"]),
        "name": str(repository["name"]),
        "aliases": [str(alias) for alias in aliases],
    }


def lint(client: CommandCenterClient, payload: dict[str, Any]) -> Any:
    return client.request("POST", "/api/v1/architecture/lint", {
        "repository": _repository(payload),
        "documents": payload["documents"],
    })


def status(client: CommandCenterClient, payload: dict[str, Any]) -> Any:
    return client.request("POST", "/api/v1/architecture/check", {
        "repository": _repository(payload)["id"],
        "source_revision": payload["source_revision"],
        "manifest_hash": payload["manifest_hash"],
        "documents": payload["hashes"],
    })


def sync(client: CommandCenterClient, payload: dict[str, Any]) -> Any:
    return client.request("POST", "/api/v1/architecture/sync", {
        "repository": _repository(payload),
        "source_revision": payload["source_revision"],
        "manifest_hash": payload["manifest_hash"],
        "documents": payload["documents"],
    })


def _summary(payload: dict[str, Any]) -> str:
    repository = _repository(payload)
    return (
        f"Repository: {repository['name']} ({repository['id']})\n"
        f"Manifest: {payload['manifest_path']}\n"
        f"Documents: {len(payload['documents'])}\n"
        f"Bytes: {payload['total_bytes']}\n"
        f"Revision: {payload['source_revision'] or '(unavailable)'}"
    )


def scaffold(
    path: Path,
    *,
    card_id: str,
    title: str,
    repository: str,
    owner_area: str,
    force: bool = False,
) -> Path:
    target = path.expanduser()
    if target.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing file: {target}")
    if target.suffix.casefold() != ".md":
        raise ValueError("architecture scaffold path must end in .md")
    target.parent.mkdir(parents=True, exist_ok=True)
    content = f"""\
---
id: {json.dumps(card_id)}
repository: {json.dumps(repository)}
title: {json.dumps(title)}
kind: architecture_doc
audience:
  - engineer
  - ai_agent
status: draft
owner_area: {json.dumps(owner_area)}
main_files: []
public_interfaces: []
provides: []
depends_on: []
safe_edit_points: []
risk_areas: []
graph_rag_entities: []
last_verified: {datetime.now(UTC).date().isoformat()}
---

# {title}

## Purpose

TODO

## Contract

TODO

## Related Docs

- TODO
"""
    target.write_text(content, encoding="utf-8")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lint, compare, or explicitly sync declared architecture.",
    )
    parser.add_argument("command", choices=("lint", "status", "sync", "scaffold"))
    parser.add_argument("repository", nargs="?", default=".")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm the explicit architecture upload for sync.",
    )
    parser.add_argument("--id", dest="card_id")
    parser.add_argument("--title")
    parser.add_argument("--repository-name")
    parser.add_argument("--owner-area", default="unspecified")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.command == "scaffold":
        if not args.card_id or not args.title or not args.repository_name:
            parser.error("scaffold requires --id, --title, and --repository-name")
        result = scaffold(
            Path(args.repository),
            card_id=args.card_id,
            title=args.title,
            repository=args.repository_name,
            owner_area=args.owner_area,
            force=args.force,
        )
        print(json.dumps({"path": str(result)}, indent=2))
        return
    payload = inventory(Path(args.repository))
    client = CommandCenterClient()
    if args.command == "lint":
        result = lint(client, payload)
    elif args.command == "status":
        result = status(client, payload)
    else:
        print(_summary(payload), file=sys.stderr)
        if not args.yes:
            answer = input("Upload only these declared Markdown documents? [y/N] ")
            if answer.strip().casefold() not in {"y", "yes"}:
                raise SystemExit("Architecture sync cancelled.")
        result = sync(client, payload)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
