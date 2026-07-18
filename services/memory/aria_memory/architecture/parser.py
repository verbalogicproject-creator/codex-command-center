from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import PurePosixPath
from typing import Any

import yaml
from markdown_it import MarkdownIt

from frontmatter_rag import ARCHITECTURE_AI_CARD_REQUIRED_SLOTS, first_h1

from .chunking import chunk_by_h2
from .models import (
    ArchitectureCard,
    ArchitectureDialect,
    ArchitectureIssue,
    ArchitectureParseResult,
    IssueSeverity,
)

MAX_DOCUMENT_BYTES = 512 * 1024
MAX_SOURCE_URI_LENGTH = 512
REQUIRED_CARD_SLOTS = ARCHITECTURE_AI_CARD_REQUIRED_SLOTS
LIST_SLOTS = (
    "audience",
    "main_files",
    "public_interfaces",
    "provides",
    "depends_on",
    "safe_edit_points",
    "risk_areas",
    "graph_rag_entities",
)
_CARD_HINTS = set(REQUIRED_CARD_SLOTS) | {
    "repository", "title", "dimensions", "relationships",
}
_FRONTMATTER = re.compile(r"^\ufeff?---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)


def _issue(
    code: str,
    severity: IssueSeverity,
    message: str,
    source_uri: str,
    *,
    field: str | None = None,
    detail: dict[str, Any] | None = None,
) -> ArchitectureIssue:
    return ArchitectureIssue(
        code=code,
        severity=severity,
        message=message,
        source_uri=source_uri,
        field=field,
        detail=detail or {},
    )


def _validate_source_uri(source_uri: str) -> None:
    if not source_uri or len(source_uri) > MAX_SOURCE_URI_LENGTH:
        raise ValueError("source_uri must be between 1 and 512 characters")
    if "\x00" in source_uri or "\\" in source_uri:
        raise ValueError("source_uri must be a repository-relative POSIX path")
    path = PurePosixPath(source_uri)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError("source_uri must not be absolute or traverse parents")


def _parse_frontmatter(
    text: str,
    source_uri: str,
    issues: list[ArchitectureIssue],
) -> tuple[dict[str, Any] | None, tuple[int, int] | None]:
    match = _FRONTMATTER.match(text)
    if not match:
        return None, None
    try:
        parsed = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        issues.append(_issue(
            "invalid_frontmatter_yaml",
            "error",
            "The YAML frontmatter could not be parsed.",
            source_uri,
            detail={"error": str(exc)[:500]},
        ))
        return None, (0, match.end())
    if not isinstance(parsed, dict):
        issues.append(_issue(
            "invalid_frontmatter_shape",
            "error",
            "Architecture frontmatter must be a mapping.",
            source_uri,
        ))
        return None, (0, match.end())
    if not (_CARD_HINTS & set(parsed)):
        return None, (0, match.end())
    return parsed, (0, match.end())


def _parse_fenced_card(
    text: str,
    source_uri: str,
    issues: list[ArchitectureIssue],
) -> tuple[dict[str, Any] | None, tuple[int, int] | None]:
    lines = text.splitlines(keepends=True)
    for token in MarkdownIt().parse(text):
        if token.type != "fence" or token.info.strip().lower() not in {"yaml", "yml"}:
            continue
        try:
            parsed = yaml.safe_load(token.content)
        except yaml.YAMLError as exc:
            if re.search(r"(?m)^\s*ai_card\s*:", token.content):
                issues.append(_issue(
                    "invalid_fenced_ai_card_yaml",
                    "error",
                    "The fenced ai_card YAML could not be parsed.",
                    source_uri,
                    detail={"error": str(exc)[:500]},
                ))
            continue
        if not isinstance(parsed, dict) or "ai_card" not in parsed:
            continue
        card = parsed["ai_card"]
        if not isinstance(card, dict):
            issues.append(_issue(
                "invalid_fenced_ai_card_shape",
                "error",
                "The fenced ai_card value must be a mapping.",
                source_uri,
            ))
            return None, None
        if token.map is None:
            return card, None
        start_line, end_line = token.map
        start = sum(len(line) for line in lines[:start_line])
        end = sum(len(line) for line in lines[:end_line])
        return card, (start, end)
    return None, None


def _string_value(
    raw: dict[str, Any],
    field: str,
    default: str,
    source_uri: str,
    issues: list[ArchitectureIssue],
) -> str:
    value = raw.get(field)
    if value is None:
        return default
    if isinstance(value, (dict, list, tuple, set)):
        issues.append(_issue(
            "invalid_scalar_field",
            "error",
            f"{field} must be a scalar value.",
            source_uri,
            field=field,
        ))
        return default
    return str(value).strip() or default


def _list_value(
    raw: dict[str, Any],
    field: str,
    source_uri: str,
    issues: list[ArchitectureIssue],
) -> list[str]:
    value = raw.get(field)
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        result: list[str] = []
        for item in value:
            if isinstance(item, (dict, list, tuple, set)):
                issues.append(_issue(
                    "invalid_list_item",
                    "error",
                    f"{field} entries must be scalar values.",
                    source_uri,
                    field=field,
                ))
                continue
            normalized = str(item).strip()
            if normalized:
                result.append(normalized)
        return result
    if isinstance(value, dict):
        issues.append(_issue(
            "invalid_list_field",
            "error",
            f"{field} must be a scalar or list of scalar values.",
            source_uri,
            field=field,
        ))
        return []
    normalized = str(value).strip()
    return [normalized] if normalized else []


def _normalize_card(
    raw_input: dict[str, Any],
    source_uri: str,
    repository: str | None,
    issues: list[ArchitectureIssue],
) -> ArchitectureCard:
    raw = copy.deepcopy(raw_input)
    missing = [field for field in REQUIRED_CARD_SLOTS if field not in raw]
    if missing:
        issues.append(_issue(
            "missing_required_slots",
            "error",
            "The architecture card is missing required slots.",
            source_uri,
            detail={"missing": missing},
        ))

    declared_id = _string_value(raw, "id", "", source_uri, issues)
    if not declared_id:
        digest = hashlib.sha256(source_uri.encode("utf-8")).hexdigest()[:16]
        declared_id = f"arch.unindexed.{digest}"
        issues.append(_issue(
            "generated_degraded_id",
            "warning",
            "A deterministic degraded ID was generated because id is missing.",
            source_uri,
            field="id",
            detail={"generated_id": declared_id},
        ))

    raw_dimensions = raw.get("dimensions")
    dimensions: dict[str, float] = {}
    if raw_dimensions is not None:
        if not isinstance(raw_dimensions, dict):
            issues.append(_issue(
                "invalid_dimensions",
                "error",
                "dimensions must be a mapping of names to numeric values.",
                source_uri,
                field="dimensions",
            ))
        else:
            for key, value in raw_dimensions.items():
                try:
                    dimensions[str(key)] = float(value)
                except (TypeError, ValueError):
                    issues.append(_issue(
                        "invalid_dimension_value",
                        "error",
                        "Every dimension value must be numeric.",
                        source_uri,
                        field=f"dimensions.{key}",
                    ))

    raw_relationships = raw.get("relationships")
    relationships: list[dict[str, Any]] = []
    if raw_relationships is not None:
        if not isinstance(raw_relationships, list):
            issues.append(_issue(
                "invalid_relationships",
                "error",
                "relationships must be a list of mappings.",
                source_uri,
                field="relationships",
            ))
        else:
            for index, value in enumerate(raw_relationships):
                if isinstance(value, dict):
                    relationships.append(copy.deepcopy(value))
                else:
                    issues.append(_issue(
                        "invalid_relationship",
                        "error",
                        "Every relationship must be a mapping.",
                        source_uri,
                        field=f"relationships.{index}",
                    ))

    last_verified = raw.get("last_verified")
    return ArchitectureCard(
        id=declared_id,
        kind=_string_value(raw, "kind", "architecture_doc", source_uri, issues),
        audience=_list_value(raw, "audience", source_uri, issues),
        status=_string_value(raw, "status", "undocumented", source_uri, issues),
        owner_area=_string_value(raw, "owner_area", "", source_uri, issues),
        main_files=_list_value(raw, "main_files", source_uri, issues),
        public_interfaces=_list_value(raw, "public_interfaces", source_uri, issues),
        provides=_list_value(raw, "provides", source_uri, issues),
        depends_on=_list_value(raw, "depends_on", source_uri, issues),
        safe_edit_points=_list_value(raw, "safe_edit_points", source_uri, issues),
        risk_areas=_list_value(raw, "risk_areas", source_uri, issues),
        graph_rag_entities=_list_value(raw, "graph_rag_entities", source_uri, issues),
        last_verified=str(last_verified).strip() if last_verified is not None else None,
        repository=_string_value(
            raw, "repository", repository or "", source_uri, issues,
        ),
        title=_string_value(raw, "title", "", source_uri, issues),
        dimensions=dimensions,
        relationships=relationships,
    )


def _strip_ranges(text: str, ranges: list[tuple[int, int]]) -> str:
    result = text
    for start, end in sorted(ranges, reverse=True):
        result = result[:start] + result[end:]
    return result.lstrip("\r\n")


def _comparison_surface(card: ArchitectureCard) -> str:
    return json.dumps(card.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def parse_architecture_document(
    text: str,
    source_uri: str,
    *,
    repository: str | None = None,
    max_bytes: int = MAX_DOCUMENT_BYTES,
) -> ArchitectureParseResult:
    """Parse, normalize, lint, and section one declared architecture document."""

    _validate_source_uri(source_uri)
    byte_count = len(text.encode("utf-8"))
    if byte_count > max_bytes:
        raise ValueError(f"architecture document exceeds {max_bytes} bytes")

    issues: list[ArchitectureIssue] = []
    front_raw, front_range = _parse_frontmatter(text, source_uri, issues)
    fenced_raw, fenced_range = _parse_fenced_card(text, source_uri, issues)

    front_card = (
        _normalize_card(front_raw, source_uri, repository, issues)
        if front_raw is not None else None
    )
    fenced_card = (
        _normalize_card(fenced_raw, source_uri, repository, issues)
        if fenced_raw is not None else None
    )

    dialect: ArchitectureDialect | None
    card: ArchitectureCard | None
    if front_card is not None and fenced_card is not None:
        if _comparison_surface(front_card) != _comparison_surface(fenced_card):
            issues.append(_issue(
                "conflicting_declarations",
                "error",
                "Frontmatter and fenced ai_card declarations do not normalize identically.",
                source_uri,
            ))
            dialect, card = None, None
        else:
            dialect, card = "dual", front_card
    elif front_card is not None:
        dialect, card = "frontmatter", front_card
    elif fenced_card is not None:
        dialect, card = "fenced-ai-card", fenced_card
    else:
        dialect, card = None, None
        issues.append(_issue(
            "missing_ai_card",
            "warning",
            "No supported architecture card declaration was found.",
            source_uri,
        ))

    ranges = [
        value for value in (front_range, fenced_range) if value is not None
    ]
    body = _strip_ranges(text, ranges)
    if card is not None and not card.title:
        card = card.model_copy(update={"title": first_h1(body) or PurePosixPath(source_uri).stem})
    sections = (
        chunk_by_h2(body, document_id=card.id, source_uri=source_uri)
        if card is not None else []
    )
    valid = card is not None and not any(issue.severity == "error" for issue in issues)
    return ArchitectureParseResult(
        source_uri=source_uri,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        dialect=dialect,
        card=card,
        body=body,
        sections=sections,
        issues=issues,
        valid=valid,
    )
