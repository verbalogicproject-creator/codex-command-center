"""Vendored declared retrieval primitives.

Adapted from declared_core 0.1.0 in frontmatter_rag commit a3b835b.
See services/memory/VENDORED.json and THIRD_PARTY_NOTICES.md.
"""

from .retrieval import (
    IntentResult,
    classify_intent,
    rrf_fuse,
    sanitize_query,
    structural_paths,
)

__all__ = [
    "IntentResult", "classify_intent", "rrf_fuse", "sanitize_query",
    "structural_paths",
]
