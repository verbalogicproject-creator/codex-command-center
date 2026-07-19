from __future__ import annotations

from pathlib import Path

from aria_memory.architecture import (
    ArchitectureBriefRequest,
    ArchitectureCompiler,
    ArchitectureStore,
    build_architecture_health,
    parse_architecture_document,
)
from aria_memory.db import Database
from aria_memory.embeddings import EmbeddingProvider, HashEmbeddingProvider


def architecture_document(
    stable_id: str,
    title: str,
    body: str,
) -> str:
    return f"""---
id: {stable_id}
repository: Synthetic Architecture
title: {title}
kind: architecture_doc
audience: [engineer, ai_agent]
status: implemented
owner_area: synthetic platform
main_files: [services/synthetic/component.py]
public_interfaces: [synthetic.run]
provides: [synthetic architecture fixture]
depends_on: []
safe_edit_points: [fixture prose]
risk_areas: [fixture drift]
graph_rag_entities: [SyntheticComponent]
last_verified: 2026-07-19
---

# {title}

## Contract

{body}
"""


def activate(store: ArchitectureStore):
    return store.activate(
        repository="Synthetic Architecture",
        repository_id="synthetic-architecture",
        aliases=["synthetic-checkout"],
        documents=[
            parse_architecture_document(
                architecture_document(
                    "synthetic.voice",
                    "Voice Component",
                    "The voice interface narrates repository evidence.",
                ),
                "docs/voice.md",
                repository="Synthetic Architecture",
            ),
            parse_architecture_document(
                architecture_document(
                    "synthetic.graph",
                    "Graph Component",
                    "The canvas displays declared dependency edges.",
                ),
                "docs/graph.md",
                repository="Synthetic Architecture",
            ),
        ],
        source_revision="dense-revision",
        manifest_hash="a" * 64,
    )


def test_sync_embeds_versioned_sections_and_fuses_dense_ranking(tmp_path: Path):
    store = ArchitectureStore(
        Database(tmp_path / "architecture.db"),
        HashEmbeddingProvider(64),
    )
    snapshot = activate(store)

    eligible, indexed, coverage = store.embeddings.coverage(snapshot.id)
    assert eligible == indexed == 2
    assert coverage == 1

    brief = ArchitectureCompiler(store).build(ArchitectureBriefRequest(
        repository="synthetic-checkout",
        mode="task",
        prompt="Improve the speaking experience",
        token_budget=1_200,
    ))

    assert brief.documents[0].title == "Voice Component"
    assert brief.health_summary["embedding_coverage"] == 1
    assert "dense_architecture_retrieval_unavailable" not in brief.degraded_reasons
    assert any(
        reason.startswith("dense similarity:")
        for source in brief.sources
        for reason in source.selection_reasons
    )


class BrokenProvider(EmbeddingProvider):
    name = "broken"
    model = "broken-v1"
    dimensions = 16

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("synthetic provider failure")

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError("synthetic provider failure")


def test_provider_failure_preserves_snapshot_and_recovers_incrementally(
    tmp_path: Path,
):
    database = Database(tmp_path / "provider-failure.db")
    broken_store = ArchitectureStore(database, BrokenProvider())
    snapshot = activate(broken_store)

    assert snapshot.status == "active"
    failed_health = build_architecture_health(
        broken_store, "synthetic-architecture",
    )
    assert failed_health.embedding_coverage == 0
    failed_brief = ArchitectureCompiler(broken_store).build(
        ArchitectureBriefRequest(
            repository="synthetic-architecture",
            prompt="speaking experience",
        )
    )
    assert "dense_architecture_retrieval_unavailable" in (
        failed_brief.degraded_reasons
    )

    recovered_store = ArchitectureStore(
        database, HashEmbeddingProvider(32),
    )
    recovered_snapshot = activate(recovered_store)
    recovered_health = build_architecture_health(
        recovered_store, "synthetic-architecture",
    )

    assert recovered_snapshot.id == snapshot.id
    assert recovered_snapshot.status == "active"
    assert recovered_health.embedding_coverage == 1


def test_embedding_coverage_is_provider_model_and_dimension_scoped(
    tmp_path: Path,
):
    database = Database(tmp_path / "scoped-coverage.db")
    first = ArchitectureStore(database, HashEmbeddingProvider(32))
    snapshot = activate(first)
    assert first.embeddings.coverage(snapshot.id)[2] == 1

    second = ArchitectureStore(database, HashEmbeddingProvider(64))
    activate(second)

    assert second.embeddings.coverage(snapshot.id)[2] == 1
    assert first.embeddings.coverage(snapshot.id)[2] == 0
