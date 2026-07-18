"""Declared tag/cluster expansion helpers adapted from declared_core 0.1.0."""

from __future__ import annotations

from typing import Iterable


def structural_paths(
    anchor: dict[str, object],
    candidate: dict[str, object],
    *,
    cluster_fields: Iterable[str],
    edge_fields: Iterable[str],
) -> list[str]:
    paths: list[str] = []
    for field in cluster_fields:
        value = anchor.get(field)
        if value and value == candidate.get(field):
            paths.append(f"{field}:{value}")
    for field in edge_fields:
        left = {str(x).lower() for x in (anchor.get(field) or [])}  # type: ignore[union-attr]
        right = {str(x).lower() for x in (candidate.get(field) or [])}  # type: ignore[union-attr]
        for shared in sorted(left & right):
            paths.append(f"{field}:{shared}")
    anchor_id = str(anchor.get("id", "")).lower()
    candidate_id = str(candidate.get("id", "")).lower()
    for field in ("depends_on", "graph_rag_entities", "main_files"):
        left = {str(x).lower() for x in (anchor.get(field) or [])}  # type: ignore[union-attr]
        right = {str(x).lower() for x in (candidate.get(field) or [])}  # type: ignore[union-attr]
        if candidate_id and candidate_id in left:
            paths.append(f"{anchor_id}->{field}->{candidate_id}")
        if anchor_id and anchor_id in right:
            paths.append(f"{candidate_id}->{field}->{anchor_id}")
    return paths
