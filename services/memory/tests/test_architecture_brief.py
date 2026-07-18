from __future__ import annotations

from pathlib import Path

from aria_memory.architecture import (
    ArchitectureBriefRequest,
    ArchitectureCompiler,
    ArchitectureStore,
    parse_architecture_document,
)
from aria_memory.db import Database

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "fixtures" / "demo" / "architecture"


def documents():
    return [
        parse_architecture_document(
            (FIXTURES / name).read_text(encoding="utf-8"),
            f"fixtures/demo/architecture/{name}",
        )
        for name in ("frontmatter-component.md", "fenced-component.md")
    ]


def compiler(tmp_path):
    store = ArchitectureStore(Database(tmp_path / "brief.db"))
    store.activate(
        repository="Synthetic Architecture",
        repository_id="synthetic-architecture",
        aliases=["synthetic-checkout"],
        documents=documents(),
        source_revision="revision-one",
        manifest_hash="a" * 64,
    )
    return ArchitectureCompiler(store)


def test_boot_brief_has_snapshot_health_and_versioned_receipts(tmp_path):
    brief = compiler(tmp_path).build(ArchitectureBriefRequest(
        repository="synthetic-checkout",
        mode="boot",
        token_budget=2_000,
    ))
    assert brief.repository_identity["id"] == "synthetic-architecture"
    assert brief.snapshot_receipt["snapshot_id"].startswith("asnap_")
    assert brief.snapshot_receipt["source_revision"] == "revision-one"
    assert brief.documents
    assert brief.sections
    assert all(source.id.startswith(("adoc_", "asec_")) for source in brief.sources)
    assert all(len(source.content_hash) == 64 for source in brief.sources)
    assert brief.token_estimate <= brief.token_budget


def test_task_brief_selects_matching_sections_and_declared_contracts(tmp_path):
    brief = compiler(tmp_path).build(ArchitectureBriefRequest(
        repository="Synthetic Architecture",
        mode="task",
        prompt="Change the fenced component contract safely",
        token_budget=2_000,
    ))
    assert brief.documents[0].title == "Fenced Component"
    assert any(section.heading == "Contract" for section in brief.sections)
    assert "fenced_component.run()" in brief.interfaces
    assert "fixture prose" in brief.safe_edit_points
    assert "fixture drift" in brief.risk_areas
    assert any(
        "declared matches" in reason
        for source in brief.sources for reason in source.selection_reasons
    )


def test_brief_is_bounded_over_fully_serialized_packet(tmp_path):
    brief = compiler(tmp_path).build(ArchitectureBriefRequest(
        repository="Synthetic Architecture",
        mode="task",
        prompt="component contract architecture fixture",
        token_budget=700,
    ))
    assert brief.token_estimate <= 700
    assert brief.omitted_candidate_count > 0


def test_unknown_repository_never_falls_back_to_other_context(tmp_path):
    brief = compiler(tmp_path).build(ArchitectureBriefRequest(
        repository="Another Repository",
        mode="task",
        prompt="component",
    ))
    assert brief.documents == []
    assert brief.sections == []
    assert brief.sources == []
    assert brief.degraded_reasons == ["repository_unregistered"]


def test_brief_api_uses_active_synced_snapshot(client):
    frontmatter = (FIXTURES / "frontmatter-component.md").read_text(encoding="utf-8")
    synced = client.post("/api/v1/architecture/sync", json={
        "repository": {
            "id": "synthetic-architecture",
            "name": "Synthetic Architecture",
            "aliases": ["synthetic-checkout"],
        },
        "source_revision": "revision-api",
        "manifest_hash": "b" * 64,
        "documents": [{
            "source_uri": "docs/frontmatter-component.md",
            "content": frontmatter,
        }],
    }).json()
    response = client.post("/api/v1/architecture/brief", json={
        "repository": "synthetic-checkout",
        "mode": "task",
        "prompt": "frontmatter contract",
        "token_budget": 1_200,
    })
    assert response.status_code == 200
    brief = response.json()
    assert brief["snapshot_receipt"]["snapshot_id"] == synced["snapshot"]["id"]
    assert brief["snapshot_receipt"]["source_revision"] == "revision-api"
