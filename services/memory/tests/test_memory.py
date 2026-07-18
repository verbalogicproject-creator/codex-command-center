from pathlib import Path

from aria_memory.db import Database
from aria_memory.embeddings import (
    EmbeddingProvider, EmbeddingStore, HashEmbeddingProvider, canonical_surface,
)
from aria_memory.store import AppStore


def test_embedding_sync_is_incremental(settings, tmp_path: Path):
    db = Database(tmp_path / "incremental.db", settings.seed_path)
    embeddings = EmbeddingStore(db, HashEmbeddingProvider())
    first = embeddings.sync()
    second = embeddings.sync()
    assert first.indexed == db.count("memories")
    assert second.indexed == 0
    assert second.unchanged == db.count("memories")


def test_embedding_surface_excludes_id(settings, tmp_path: Path):
    db = Database(tmp_path / "surface.db", settings.seed_path)
    memory = db.get_memory("fact_pm_01")
    assert memory
    surface = canonical_surface(memory)
    assert memory.id not in surface
    assert memory.project in surface
    assert memory.content in surface


class BrokenProvider(EmbeddingProvider):
    name, model, dimensions = "broken", "broken-256", 256

    def embed_documents(self, texts):
        raise RuntimeError("offline")

    def embed_query(self, text):
        raise RuntimeError("offline")


def test_provider_failure_leaves_pending(settings, tmp_path: Path):
    db = Database(tmp_path / "broken.db", settings.seed_path)
    embeddings = EmbeddingStore(db, BrokenProvider())
    result = embeddings.sync()
    assert result.failed == db.count("memories")
    assert result.status.pending == db.count("memories")
    assert result.status.degraded is True


def test_proposal_confirmation_is_idempotent(settings, tmp_path: Path):
    db = Database(tmp_path / "proposal.db", settings.seed_path)
    store = AppStore(db)
    session = store.create_session("Test")
    before = db.count("memories")
    proposal = store.create_proposal(
        session.id, "record_fact",
        {"project": "Command Center", "kind": "decision", "title": "Use evidence",
         "content": "Every synthesis retains inspectable evidence."},
        "Review decision", ["fact_pm_01"],
    )
    assert proposal.status == "pending"
    confirmed = store.confirm(proposal.id)
    repeated = store.confirm(proposal.id)
    assert confirmed.status == repeated.status == "confirmed"
    assert confirmed.memory_id == repeated.memory_id
    assert db.count("memories") == before + 1


def test_rejection_does_not_mutate_memory(settings, tmp_path: Path):
    db = Database(tmp_path / "reject.db", settings.seed_path)
    store = AppStore(db)
    before = db.count("memories")
    proposal = store.create_proposal(
        None, "record_fact",
        {"project": "Command Center", "title": "No", "content": "No"},
        "Should be rejected", [],
    )
    assert store.reject(proposal.id).status == "rejected"
    assert db.count("memories") == before
    assert any(item.action == "proposal.rejected" for item in store.audit())


def test_mud_guard_refuses_conflicting_merge(settings, tmp_path: Path):
    db = Database(tmp_path / "mud.db", settings.seed_path)
    store = AppStore(db)
    before = db.count("memories")
    proposal = store.create_proposal(
        None, "record_fact",
        {"project": "Command Center", "kind": "decision",
         "title": "Merge LifeOS into Command Center",
         "content": "Merge LifeOS and Hexagon into one application."},
        "Conflicting synthesis", ["fact_life_06", "fact_hex_07"],
    )
    try:
        store.confirm(proposal.id)
        raise AssertionError("guard should refuse")
    except ValueError as exc:
        assert "MUD guard" in str(exc)
    assert db.count("memories") == before
    assert store.get_proposal(proposal.id).status == "failed"
    assert any(item.action == "proposal.failed" for item in store.audit())
