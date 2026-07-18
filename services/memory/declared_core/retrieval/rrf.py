"""Weighted reciprocal rank fusion from declared_core 0.1.0."""

from __future__ import annotations

from typing import Any, Sequence


def rrf_fuse(
    ranked_lists: Sequence[list[dict[str, Any]]],
    *,
    weights: Sequence[float] | None = None,
    labels: Sequence[str] | None = None,
    k: int = 60,
) -> list[dict[str, Any]]:
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    if len(weights) != len(ranked_lists):
        raise ValueError("weights length must match ranked lists")
    if labels is not None and len(labels) != len(ranked_lists):
        raise ValueError("labels length must match ranked lists")
    fused: dict[tuple[str, str], dict[str, Any]] = {}
    for list_index, (items, weight) in enumerate(zip(ranked_lists, weights, strict=True)):
        if not weight:
            continue
        for rank, item in enumerate(items, start=1):
            key = (str(item.get("table", "")), str(item.get("id", "")))
            slot = fused.setdefault(key, {**item, "rrf_score": 0.0, "rrf_sources": []})
            slot["rrf_score"] += weight / (k + rank)
            label = labels[list_index] if labels else "unknown"
            if label == "structural" and item.get("structural_paths"):
                label = "structural:" + str(item["structural_paths"][0])
            if label not in slot["rrf_sources"]:
                slot["rrf_sources"].append(label)
    return sorted(fused.values(), key=lambda item: item["rrf_score"], reverse=True)
