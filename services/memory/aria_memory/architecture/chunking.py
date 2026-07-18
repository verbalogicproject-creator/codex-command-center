from __future__ import annotations

import hashlib
import re

from markdown_it import MarkdownIt

from .models import ArchitectureSection

_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _slugify(heading: str, ordinal: int) -> str:
    value = heading.strip().lower().replace("_", "-").replace(" ", "-")
    value = _SLUG_RE.sub("-", value).strip("-")[:80]
    return value or f"section-{ordinal}"


def chunk_by_h2(
    markdown_text: str,
    *,
    document_id: str,
    source_uri: str,
) -> list[ArchitectureSection]:
    """Return deterministic H2 sections without splitting inside code fences."""

    tokens = MarkdownIt().parse(markdown_text)
    starts: list[int] = []
    headings: list[str] = []
    waiting_for_heading = False
    for token in tokens:
        if token.type == "heading_open" and token.tag == "h2":
            waiting_for_heading = True
            if token.map is not None:
                starts.append(token.map[0])
        elif waiting_for_heading and token.type == "inline":
            headings.append(token.content.strip())
            waiting_for_heading = False

    lines = markdown_text.splitlines()
    seen_slugs: dict[str, int] = {}
    sections: list[ArchitectureSection] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(lines)
        heading = headings[index] if index < len(headings) else ""
        base_slug = _slugify(heading, index + 1)
        seen_slugs[base_slug] = seen_slugs.get(base_slug, 0) + 1
        duplicate = seen_slugs[base_slug]
        slug = base_slug if duplicate == 1 else f"{base_slug}-{duplicate}"
        body = "\n".join(lines[start:end]).strip()
        sections.append(ArchitectureSection(
            id=f"{document_id}#{slug}",
            document_id=document_id,
            source_uri=source_uri,
            heading=heading,
            heading_slug=slug,
            ordinal=index,
            body=body,
            content_hash=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        ))
    return sections
