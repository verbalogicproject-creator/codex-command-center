"""Frontmatter role declaration adapted from frontmatter_rag 0.1.0."""

from __future__ import annotations

import re
from dataclasses import dataclass

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


@dataclass(frozen=True)
class Facet:
    key: str
    role: str = "text"

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.key):
            raise ValueError(f"invalid facet key: {self.key}")
        if self.role not in {"text", "tag", "cluster", "carry"}:
            raise ValueError(f"invalid facet role: {self.role}")


@dataclass(frozen=True)
class FrontmatterSchema:
    facets: tuple[Facet, ...]
    id_key: str = "id"
    title_key: str | None = "title"
    timestamp_key: str | None = "last_verified"

    @property
    def searchable(self) -> tuple[str, ...]:
        return tuple(f.key for f in self.facets if f.role == "text")

    @property
    def edges(self) -> tuple[str, ...]:
        return tuple(f.key for f in self.facets if f.role == "tag")

    @property
    def clusters(self) -> tuple[str, ...]:
        return tuple(f.key for f in self.facets if f.role == "cluster")
