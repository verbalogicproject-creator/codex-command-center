from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .models import ArchitectureRepositoryIdentity, ArchitectureSyncDocument
from .parser import MAX_DOCUMENT_BYTES

MANIFEST_RELATIVE_PATHS = (
    Path(".command-center/architecture.yaml"),
    Path(".command-center/architecture.yml"),
)
MAX_DOCUMENT_COUNT = 1_000
MAX_CORPUS_BYTES = 20 * 1024 * 1024


class ArchitectureDocumentRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roots: list[str] = Field(min_length=1, max_length=40)
    patterns: list[str] = Field(
        default_factory=lambda: ["**/*.md"],
        min_length=1,
        max_length=40,
    )
    exclude: list[str] = Field(default_factory=list, max_length=100)


class ArchitectureManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1, le=1)
    repository: ArchitectureRepositoryIdentity
    documents: ArchitectureDocumentRules
    dialects: list[str] = Field(
        default_factory=lambda: ["frontmatter", "fenced-ai-card"],
        min_length=1,
        max_length=2,
    )


@dataclass(frozen=True)
class ArchitectureInventory:
    repository_root: Path
    manifest_path: Path
    manifest: ArchitectureManifest
    manifest_hash: str
    source_revision: str
    documents: tuple[ArchitectureSyncDocument, ...]

    @property
    def content_hashes(self) -> dict[str, str]:
        return {
            document.source_uri: hashlib.sha256(
                document.content.encode("utf-8")
            ).hexdigest()
            for document in self.documents
        }


def find_repository_root(start: Path) -> tuple[Path, Path]:
    current = start.expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        for relative in MANIFEST_RELATIVE_PATHS:
            manifest_path = candidate / relative
            if manifest_path.is_file():
                return candidate, manifest_path
    raise FileNotFoundError(
        "No .command-center/architecture.yaml manifest found in this checkout."
    )


def _safe_relative(value: str, field: str) -> PurePosixPath:
    if not value or "\\" in value or "\x00" in value:
        raise ValueError(f"{field} must be a repository-relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field} must not be absolute or traverse parents")
    return path


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _excluded(source_uri: str, patterns: list[str]) -> bool:
    path = PurePosixPath(source_uri)
    return any(path.match(pattern) for pattern in patterns)


def _git_revision(root: Path) -> str:
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


def load_architecture_manifest(path: Path) -> tuple[ArchitectureManifest, str]:
    raw = path.read_bytes()
    parsed = yaml.safe_load(raw)
    if not isinstance(parsed, dict):
        raise ValueError("architecture manifest must be a YAML mapping")
    manifest = ArchitectureManifest.model_validate(parsed)
    unknown_dialects = set(manifest.dialects) - {
        "frontmatter", "fenced-ai-card",
    }
    if unknown_dialects:
        raise ValueError(
            "unsupported architecture dialects: "
            + ", ".join(sorted(unknown_dialects))
        )
    return manifest, hashlib.sha256(raw).hexdigest()


def scan_architecture_repository(start: Path) -> ArchitectureInventory:
    root, manifest_path = find_repository_root(start)
    manifest, manifest_hash = load_architecture_manifest(manifest_path)
    root = root.resolve()

    for pattern in [*manifest.documents.patterns, *manifest.documents.exclude]:
        _safe_relative(pattern, "document pattern")
    candidates: dict[str, Path] = {}
    for raw_root in manifest.documents.roots:
        relative_root = _safe_relative(raw_root, "document root")
        document_root = (root / Path(*relative_root.parts)).resolve()
        if not _inside(root, document_root):
            raise ValueError("document root escapes the repository")
        if not document_root.exists():
            continue
        for pattern in manifest.documents.patterns:
            for path in document_root.glob(pattern):
                if not path.is_file():
                    continue
                resolved = path.resolve()
                if not _inside(root, resolved):
                    raise ValueError("architecture document symlink escapes the repository")
                source_uri = resolved.relative_to(root).as_posix()
                if _excluded(source_uri, manifest.documents.exclude):
                    continue
                if resolved.suffix.casefold() != ".md":
                    raise ValueError("architecture sync accepts Markdown documents only")
                candidates[source_uri] = resolved

    if len(candidates) > MAX_DOCUMENT_COUNT:
        raise ValueError(
            f"architecture corpus exceeds {MAX_DOCUMENT_COUNT} documents"
        )
    documents: list[ArchitectureSyncDocument] = []
    total_bytes = 0
    for source_uri, path in sorted(candidates.items()):
        raw = path.read_bytes()
        if len(raw) > MAX_DOCUMENT_BYTES:
            raise ValueError(
                f"architecture document exceeds {MAX_DOCUMENT_BYTES} bytes: {source_uri}"
            )
        total_bytes += len(raw)
        if total_bytes > MAX_CORPUS_BYTES:
            raise ValueError(
                f"architecture corpus exceeds {MAX_CORPUS_BYTES} bytes"
            )
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"architecture document is not UTF-8: {source_uri}"
            ) from exc
        documents.append(ArchitectureSyncDocument(
            source_uri=source_uri,
            content=content,
        ))
    if not documents:
        raise ValueError("architecture manifest selected no documents")
    return ArchitectureInventory(
        repository_root=root,
        manifest_path=manifest_path,
        manifest=manifest,
        manifest_hash=manifest_hash,
        source_revision=_git_revision(root),
        documents=tuple(documents),
    )
