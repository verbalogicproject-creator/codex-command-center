#!/usr/bin/env python3
"""Build the public Command Center atlas from repository truth.

The narrative and claim mapping are curated. Routes, Python symbols, tables,
tests, source locations, excerpts, and coverage counts are extracted and
validated on every build.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import html
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/atlas/claims.json"
TEMPLATE = ROOT / "docs/atlas/template.html"
OUTPUT = ROOT / "apps/web/public/atlas/index.html"
LEGACY_OUTPUT = ROOT / "docs/command-center-atlas.html"
PYTHON_ROOT = ROOT / "services/memory/aria_memory"
TEST_ROOT = ROOT / "services/memory/tests"
SOURCE_BASE = "https://github.com/verbalogicproject-creator/codex-command-center/blob"
MAX_EXCERPT_LINES = 18


class AtlasError(RuntimeError):
    pass


@dataclass(frozen=True)
class Symbol:
    path: str
    name: str
    kind: str
    line: int
    end_line: int

    @property
    def id(self) -> str:
        return f"symbol:{self.path}::{self.name}"


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise AtlasError(f"Could not read {relative(path)}: {exc}") from exc


def source_url(path: str, line: int = 1) -> str:
    ref = os.environ.get("ATLAS_RELEASE_REF", "main")
    return f"{SOURCE_BASE}/{ref}/{path}#L{line}"


def parse_symbols(path: Path) -> tuple[list[Symbol], ast.Module]:
    text = read_text(path)
    try:
        tree = ast.parse(text, filename=relative(path))
    except SyntaxError as exc:
        raise AtlasError(f"Could not parse {relative(path)}: {exc}") from exc
    found: list[Symbol] = []

    def walk(body: Iterable[ast.stmt], parents: tuple[str, ...] = ()) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = ".".join((*parents, node.name))
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                found.append(
                    Symbol(
                        relative(path),
                        name,
                        kind,
                        node.lineno,
                        getattr(node, "end_lineno", node.lineno),
                    )
                )
                if isinstance(node, ast.ClassDef):
                    walk(node.body, (*parents, node.name))

    walk(tree.body)
    return found, tree


def decorator_route(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, str] | None:
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
            continue
        method = decorator.func.attr.upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"} or not decorator.args:
            continue
        path = decorator.args[0]
        if isinstance(path, ast.Constant) and isinstance(path.value, str):
            return method, path.value
    return None


def extract_routes(python_files: list[Path]) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    for path in python_files:
        _, tree = parse_symbols(path)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            route = decorator_route(node)
            if not route:
                continue
            method, uri = route
            source_path = relative(path)
            routes.append(
                {
                    "id": f"route:{method} {uri}",
                    "kind": "route",
                    "name": f"{method} {uri}",
                    "method": method,
                    "route": uri,
                    "path": source_path,
                    "line": node.lineno,
                    "symbol": node.name,
                    "url": source_url(source_path, node.lineno),
                }
            )
    return sorted(routes, key=lambda item: (item["route"], item["method"]))


TABLE_RE = re.compile(
    r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"']?([a-z][a-z0-9_]*)",
    re.IGNORECASE,
)


def extract_tables(python_files: list[Path]) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for path in python_files:
        text = read_text(path)
        lines = text.splitlines()
        for match in TABLE_RE.finditer(text):
            name = match.group(1)
            line = text.count("\n", 0, match.start()) + 1
            item = by_name.setdefault(
                name,
                {
                    "id": f"table:{name}",
                    "kind": "table",
                    "name": name,
                    "locations": [],
                },
            )
            location = {
                "path": relative(path),
                "line": line,
                "url": source_url(relative(path), line),
                "engine": "PostgreSQL" if path.name == "postgres.py" else "SQLite",
            }
            if location not in item["locations"]:
                item["locations"].append(location)
            definition = "\n".join(lines[line - 1 : line + 10])
            columns = []
            for column in re.findall(
                r"^\s*([a-z][a-z0-9_]*)\s+(?:TEXT|INTEGER|REAL|BLOB|BYTEA|BOOLEAN|JSONB)\b",
                definition,
                re.MULTILINE | re.IGNORECASE,
            ):
                if column.lower() not in columns:
                    columns.append(column.lower())
            if columns:
                item.setdefault("columns", columns)
    return sorted(by_name.values(), key=lambda item: item["name"])


def extract_app_migration() -> int:
    path = PYTHON_ROOT / "db.py"
    _, tree = parse_symbols(path)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == "APP_MIGRATION_VERSION" for target in node.targets):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, int):
                return node.value.value
    raise AtlasError("APP_MIGRATION_VERSION was not found in db.py")


def literal(node: ast.AST | None, default: Any = None) -> Any:
    if node is None:
        return default
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return default


def extract_commands() -> list[dict[str, Any]]:
    path = PYTHON_ROOT / "aria_registry.py"
    _, tree = parse_symbols(path)
    manifest_node: ast.List | None = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "COMMAND_MANIFEST"
            for target in node.targets
        ) and isinstance(node.value, ast.List):
            manifest_node = node.value
            break
    if manifest_node is None:
        raise AtlasError("COMMAND_MANIFEST was not found in aria_registry.py")
    commands: list[dict[str, Any]] = []
    for item in manifest_node.elts:
        if not isinstance(item, ast.Call) or not item.args:
            continue
        name = literal(item.args[0])
        if not isinstance(name, str):
            continue
        keywords = {keyword.arg: keyword.value for keyword in item.keywords if keyword.arg}
        scopes = literal(item.args[2] if len(item.args) > 2 else None, [])
        commands.append(
            {
                "id": f"command:{name}",
                "kind": "command",
                "name": name,
                "path": relative(path),
                "line": item.lineno,
                "url": source_url(relative(path), item.lineno),
                "description": literal(item.args[1] if len(item.args) > 1 else None, ""),
                "scopes": scopes if isinstance(scopes, list) else [],
                "safety": literal(keywords.get("safety"), "standard"),
                "confirmation": literal(keywords.get("confirmation"), "none"),
                "eligible": bool(literal(keywords.get("eligible"), True)),
            }
        )
    return commands


def excerpt(path: Path, start: int, end: int) -> dict[str, Any]:
    lines = read_text(path).splitlines()
    first = max(1, start)
    last = min(len(lines), end, first + MAX_EXCERPT_LINES - 1)
    return {
        "start": first,
        "end": last,
        "text": "\n".join(lines[first - 1 : last]),
    }


def needle_excerpt(path: Path, needle: str) -> tuple[int, dict[str, Any]]:
    text = read_text(path)
    index = text.casefold().find(needle.casefold())
    if index < 0:
        raise AtlasError(f"Needle {needle!r} was not found in {relative(path)}")
    line = text.count("\n", 0, index) + 1
    return line, excerpt(path, line - 3, line + 5)


def source_node_for_support(
    support: dict[str, Any],
    symbols: dict[tuple[str, str], Symbol],
    routes: dict[tuple[str, str], dict[str, Any]],
    tables: dict[str, dict[str, Any]],
    tests: dict[tuple[str, str], Symbol],
) -> dict[str, Any]:
    kind = support.get("kind")
    if kind == "symbol":
        key = (support["path"], support["name"])
        symbol = symbols.get(key)
        if not symbol:
            raise AtlasError(f"Missing symbol {support['name']} in {support['path']}")
        path = ROOT / symbol.path
        return {
            "id": symbol.id,
            "kind": "symbol",
            "name": symbol.name,
            "path": symbol.path,
            "line": symbol.line,
            "url": source_url(symbol.path, symbol.line),
            "excerpt": excerpt(path, symbol.line, symbol.end_line),
        }
    if kind == "test":
        key = (support["path"], support["name"])
        symbol = tests.get(key)
        if not symbol:
            raise AtlasError(f"Missing test {support['name']} in {support['path']}")
        path = ROOT / symbol.path
        return {
            "id": f"test:{symbol.path}::{symbol.name}",
            "kind": "test",
            "name": symbol.name,
            "path": symbol.path,
            "line": symbol.line,
            "url": source_url(symbol.path, symbol.line),
            "excerpt": excerpt(path, symbol.line, symbol.end_line),
        }
    if kind == "route":
        key = (support["method"].upper(), support["path"])
        route = routes.get(key)
        if not route:
            raise AtlasError(f"Missing route {key[0]} {key[1]}")
        symbol = symbols.get((route["path"], route["symbol"]))
        end_line = symbol.end_line if symbol else route["line"] + MAX_EXCERPT_LINES
        return {
            **route,
            "excerpt": excerpt(ROOT / route["path"], route["line"], end_line),
        }
    if kind == "table":
        table = tables.get(support["name"])
        if not table:
            raise AtlasError(f"Missing table {support['name']}")
        location = table["locations"][0]
        return {
            **table,
            "path": location["path"],
            "line": location["line"],
            "url": location["url"],
            "excerpt": excerpt(ROOT / location["path"], location["line"], location["line"] + 12),
        }
    if kind in {"file", "doc"}:
        path = ROOT / support["path"]
        if not path.is_file():
            raise AtlasError(f"Missing {kind} {support['path']}")
        line, selected = needle_excerpt(path, support["needle"])
        return {
            "id": f"{kind}:{support['path']}#{support['needle']}",
            "kind": kind,
            "name": Path(support["path"]).name,
            "path": support["path"],
            "line": line,
            "url": source_url(support["path"], line),
            "excerpt": selected,
        }
    raise AtlasError(f"Unsupported claim source kind: {kind!r}")


def module_summary(path: Path, symbols: list[Symbol]) -> dict[str, Any]:
    text = read_text(path)
    docstring = ast.get_docstring(ast.parse(text)) or ""
    first_sentence = docstring.split("\n", 1)[0][:180]
    return {
        "id": f"module:{relative(path)}",
        "kind": "module",
        "name": path.stem,
        "path": relative(path),
        "line": 1,
        "url": source_url(relative(path), 1),
        "summary": first_sentence,
        "symbols": len(symbols),
        "lines": len(text.splitlines()),
    }


def build_data() -> dict[str, Any]:
    try:
        manifest = json.loads(read_text(MANIFEST))
    except json.JSONDecodeError as exc:
        raise AtlasError(f"Invalid {relative(MANIFEST)}: {exc}") from exc

    python_files = sorted(
        path for path in PYTHON_ROOT.rglob("*.py") if "__pycache__" not in path.parts
    )
    test_files = sorted(TEST_ROOT.glob("test_*.py"))
    all_symbols: list[Symbol] = []
    symbols_by_file: dict[str, list[Symbol]] = {}
    for path in python_files:
        found, _ = parse_symbols(path)
        all_symbols.extend(found)
        symbols_by_file[relative(path)] = found
    test_symbols: list[Symbol] = []
    for path in test_files:
        found, _ = parse_symbols(path)
        test_symbols.extend(symbol for symbol in found if symbol.name.startswith("test_"))

    routes_list = extract_routes(python_files)
    tables_list = extract_tables(python_files)
    symbol_lookup = {(item.path, item.name): item for item in all_symbols}
    test_lookup = {(item.path, item.name): item for item in test_symbols}
    route_lookup = {(item["method"], item["route"]): item for item in routes_list}
    table_lookup = {item["name"]: item for item in tables_list}

    source_catalog: dict[str, dict[str, Any]] = {}
    claims: list[dict[str, Any]] = []
    reverse_claims: dict[str, list[str]] = {}
    claim_ids: set[str] = set()
    layer_ids = {item["id"] for item in manifest["grounding_layers"]}

    for claim in manifest["claims"]:
        if claim["id"] in claim_ids:
            raise AtlasError(f"Duplicate claim id {claim['id']}")
        claim_ids.add(claim["id"])
        if claim["layer"] not in layer_ids:
            raise AtlasError(f"Claim {claim['id']} has unknown layer {claim['layer']}")
        resolved_ids: list[str] = []
        for support in claim["supports"]:
            node = source_node_for_support(
                support, symbol_lookup, route_lookup, table_lookup, test_lookup
            )
            source_catalog[node["id"]] = node
            resolved_ids.append(node["id"])
            reverse_claims.setdefault(node["id"], []).append(claim["id"])
        has_test = any(
            source_catalog[item]["kind"] == "test"
            or ".test." in source_catalog[item].get("path", "")
            or source_catalog[item].get("path", "").startswith("services/memory/tests/")
            for item in resolved_ids
        )
        if not resolved_ids or not has_test:
            raise AtlasError(f"Claim {claim['id']} must resolve to implementation and test sources")
        claims.append({
            **claim,
            "implementation_status": claim.get("implementation_status", "implemented"),
            "source_ids": resolved_ids,
            "grounding_path": [
                {
                    "kind": source_catalog[source_id]["kind"],
                    "source_id": source_id,
                    "source": source_catalog[source_id].get(
                        "path", source_catalog[source_id]["name"]
                    ),
                }
                for source_id in resolved_ids
            ],
        })

    modules = [
        module_summary(path, symbols_by_file[relative(path)]) for path in python_files
    ]
    claims_by_path: dict[str, set[str]] = {}
    for source_id, claim_ids_for_source in reverse_claims.items():
        source_catalog[source_id]["claim_ids"] = sorted(set(claim_ids_for_source))
        source_path = source_catalog[source_id].get("path")
        if source_path:
            claims_by_path.setdefault(source_path, set()).update(claim_ids_for_source)
    tests = [
        {
            "id": f"test:{item.path}::{item.name}",
            "kind": "test",
            "name": item.name,
            "path": item.path,
            "line": item.line,
            "url": source_url(item.path, item.line),
        }
        for item in test_symbols
    ]
    symbols = [
        {
            "id": item.id,
            "kind": item.kind,
            "name": item.name,
            "path": item.path,
            "line": item.line,
            "url": source_url(item.path, item.line),
        }
        for item in all_symbols
    ]
    commands = extract_commands()
    for collection in (modules, symbols, routes_list, tables_list, tests, commands):
        for item in collection:
            item["claim_ids"] = sorted(
                set(reverse_claims.get(item["id"], []))
                | claims_by_path.get(item.get("path", ""), set())
                if item["kind"] == "module"
                else set(reverse_claims.get(item["id"], []))
            )

    reference_paths = {
        ROOT / support["path"]
        for claim in manifest["claims"]
        for support in claim["supports"]
        if "path" in support and not str(support["path"]).startswith("/")
    }
    snapshot_inputs = [
        Path(__file__).resolve(), MANIFEST, TEMPLATE, *python_files, *test_files,
        *sorted(reference_paths),
    ]
    snapshot = hashlib.sha256()
    for path in sorted(snapshot_inputs):
        snapshot.update(relative(path).encode())
        snapshot.update(b"\0")
        snapshot.update(path.read_bytes())
        snapshot.update(b"\0")

    snapshot_hash = snapshot.hexdigest()
    for claim in claims:
        claim["receipt"] = {
            "schema_version": manifest["schema_version"],
            "claim_id": claim["id"],
            "claim": claim["title"],
            "implementation_status": claim["implementation_status"],
            "source_revision": os.environ.get("ATLAS_RELEASE_REF", "main"),
            "snapshot_hash": snapshot_hash,
            "grounding_path": claim["grounding_path"],
            "failure_behavior": claim["failure"],
        }

    climax_claim_id = manifest["climax_claim_id"]
    if climax_claim_id not in claim_ids:
        raise AtlasError(f"Unknown climax claim id {climax_claim_id}")

    return {
        "schema_version": manifest["schema_version"],
        "title": manifest["title"],
        "subtitle": manifest["subtitle"],
        "repository_url": manifest["repository_url"],
        "origin_url": manifest["origin_url"],
        "release_ref": os.environ.get("ATLAS_RELEASE_REF", "main"),
        "snapshot_hash": snapshot_hash,
        "climax_claim_id": climax_claim_id,
        "migration": extract_app_migration(),
        "counts": {
            "claims": len(claims),
            "modules": len(modules),
            "symbols": len(all_symbols),
            "routes": len(routes_list),
            "tables": len(tables_list),
            "tests": len(tests),
            "commands": len(commands),
        },
        "grounding_layers": manifest["grounding_layers"],
        "claims": claims,
        "sources": sorted(source_catalog.values(), key=lambda item: (item["kind"], item["path"], item["line"])),
        "modules": modules,
        "symbols": symbols,
        "routes": routes_list,
        "tables": tables_list,
        "tests": tests,
        "commands": commands,
        "lineage": manifest["lineage"],
    }


def render(data: dict[str, Any]) -> str:
    template = read_text(TEMPLATE)
    marker = "__ATLAS_DATA__"
    if template.count(marker) != 1:
        raise AtlasError(f"{relative(TEMPLATE)} must contain exactly one {marker} marker")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    return template.replace(marker, payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail when generated output is stale")
    parser.add_argument("--json", action="store_true", help="Print the extracted snapshot as JSON")
    args = parser.parse_args()
    try:
        data = build_data()
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return 0
        rendered = render(data)
        if args.check:
            if not OUTPUT.is_file() or read_text(OUTPUT) != rendered:
                raise AtlasError(
                    f"{relative(OUTPUT)} is stale; run python scripts/build_atlas.py"
                )
            print(
                "Atlas verified: "
                f"{data['counts']['claims']} claims, {data['counts']['modules']} modules, "
                f"{data['counts']['routes']} routes, {data['counts']['tables']} tables, "
                f"{data['counts']['tests']} tests."
            )
            return 0
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(rendered, encoding="utf-8")
        if LEGACY_OUTPUT.exists():
            LEGACY_OUTPUT.write_text(rendered, encoding="utf-8")
        print(f"Wrote {relative(OUTPUT)} ({len(rendered):,} bytes)")
        return 0
    except AtlasError as exc:
        print(f"atlas: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
