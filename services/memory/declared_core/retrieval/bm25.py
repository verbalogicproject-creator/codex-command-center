"""FTS5 query sanitization from declared_core 0.1.0."""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def sanitize_query(query: str) -> str:
    """Return a MATCH-safe OR query; punctuation never reaches FTS grammar."""
    return " OR ".join(f'"{token}"' for token in _TOKEN_RE.findall(query or ""))
