from __future__ import annotations

from datetime import UTC, date, datetime

import yaml
from pydantic import BaseModel, Field

from .models import ArchitectureDialect, ArchitectureIssue
from .parser import parse_architecture_document


class ArchitectureLintReport(BaseModel):
    source_uri: str
    valid: bool
    dialect: ArchitectureDialect | None
    card_id: str | None
    section_count: int
    content_hash: str
    issues: list[ArchitectureIssue] = Field(default_factory=list)


def lint_architecture_document(
    text: str,
    source_uri: str,
    *,
    repository: str | None = None,
) -> ArchitectureLintReport:
    result = parse_architecture_document(
        text, source_uri, repository=repository,
    )
    return ArchitectureLintReport(
        source_uri=source_uri,
        valid=result.valid,
        dialect=result.dialect,
        card_id=result.card.id if result.card else None,
        section_count=len(result.sections),
        content_hash=result.content_hash,
        issues=result.issues,
    )


def scaffold_ai_card(
    *,
    card_id: str,
    title: str,
    repository: str,
    kind: str = "architecture_doc",
    audience: list[str] | None = None,
    status: str = "draft",
    owner_area: str = "unspecified",
    last_verified: date | None = None,
) -> str:
    """Return a complete 13-slot frontmatter architecture document."""

    verified = last_verified or datetime.now(UTC).date()
    card = {
        "id": card_id,
        "repository": repository,
        "title": title,
        "kind": kind,
        "audience": audience or ["engineer", "ai_agent"],
        "status": status,
        "owner_area": owner_area,
        "main_files": [],
        "public_interfaces": [],
        "provides": [],
        "depends_on": [],
        "safe_edit_points": [],
        "risk_areas": [],
        "graph_rag_entities": [],
        "last_verified": verified.isoformat(),
    }
    frontmatter = yaml.safe_dump(card, sort_keys=False, allow_unicode=True).strip()
    return (
        f"---\n{frontmatter}\n---\n\n"
        f"# {title}\n\n"
        "## Purpose\n\nTODO\n\n"
        "## Contract\n\nTODO\n\n"
        "## Related Docs\n\n- TODO\n"
    )
