from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from aria_memory.architecture import ArchitectureStore, parse_architecture_document
from aria_memory.db import APP_MIGRATION_VERSION, Database

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "fixtures" / "demo" / "architecture"


def parsed_fixture(name: str):
    return parse_architecture_document(
        (FIXTURES / name).read_text(encoding="utf-8"),
        f"fixtures/demo/architecture/{name}",
    )


@pytest.fixture
def architecture_db(tmp_path: Path) -> Database:
    return Database(tmp_path / "architecture.db")


@pytest.fixture
def architecture_store(architecture_db: Database) -> ArchitectureStore:
    return ArchitectureStore(architecture_db)


def test_empty_and_v4_databases_apply_ordered_app_migrations(tmp_path: Path):
    empty = Database(tmp_path / "empty.db")
    with empty.connect() as conn:
        versions = [
            row[0] for row in conn.execute(
                "SELECT version FROM app_migrations ORDER BY version"
            )
        ]
    assert versions == [4, 5, 6, 7, APP_MIGRATION_VERSION]

    previous_path = tmp_path / "previous.db"
    with sqlite3.connect(previous_path) as conn:
        conn.execute(
            "CREATE TABLE app_migrations(version INTEGER PRIMARY KEY, applied_at TEXT)"
        )
        conn.execute("INSERT INTO app_migrations VALUES(4,'earlier')")
    upgraded = Database(previous_path)
    with upgraded.connect() as conn:
        versions = [
            row[0] for row in conn.execute(
                "SELECT version FROM app_migrations ORDER BY version"
            )
        ]
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert versions == [4, 5, 6, 7, APP_MIGRATION_VERSION]
    assert {
        "architecture_snapshots",
        "architecture_document_versions",
        "architecture_sections",
        "architecture_edges",
        "architecture_issues",
    } <= tables
    with upgraded.connect() as conn:
        columns = {
            row[1] for row in conn.execute(
                "PRAGMA table_info(handoffs)"
            ).fetchall()
        }
    assert columns >= {"planning_receipt_json", "visual_brief_json"}


def test_snapshot_activation_persists_versions_sections_edges_and_issues(
    architecture_store: ArchitectureStore,
):
    snapshot = architecture_store.activate(
        repository="Synthetic Architecture",
        documents=[
            parsed_fixture("frontmatter-component.md"),
            parsed_fixture("fenced-component.md"),
        ],
        source_revision="revision-one",
        manifest_hash="manifest-one",
    )

    assert snapshot.status == "active"
    assert snapshot.document_count == snapshot.valid_count == 2
    assert len(architecture_store.list_document_versions(snapshot.id)) == 2
    assert len(architecture_store.list_sections(snapshot.id)) == 4

    edges = architecture_store.list_edges(snapshot.id)
    assert {"CONTAINS", "PART_OF", "DESCRIBES", "OWNS_CONTRACT", "PROVIDES",
            "DEPENDS_ON", "SAFE_EDIT_POINT", "RISK_AREA", "MENTIONS"} <= {
        edge.relation_type for edge in edges
    }
    dependency_edges = [
        edge for edge in edges if edge.relation_type == "DEPENDS_ON"
    ]
    assert dependency_edges
    assert all(edge.resolution_status == "unresolved" for edge in dependency_edges)
    assert {issue.code for issue in architecture_store.list_issues(snapshot.id)} == {
        "unresolved_edge"
    }


def test_identical_resync_is_idempotent(architecture_store: ArchitectureStore):
    documents = [parsed_fixture("frontmatter-component.md")]
    first = architecture_store.activate(
        repository="Synthetic Architecture",
        documents=documents,
        source_revision="same",
        manifest_hash="manifest",
    )
    second = architecture_store.activate(
        repository="Synthetic Architecture",
        documents=documents,
        source_revision="same",
        manifest_hash="manifest",
    )
    assert first == second
    assert len(architecture_store.list_snapshots("Synthetic Architecture")) == 1


def test_new_snapshot_keeps_old_evidence_byte_resolvable(
    architecture_store: ArchitectureStore,
):
    original = parsed_fixture("frontmatter-component.md")
    first = architecture_store.activate(
        repository="Synthetic Architecture",
        documents=[original],
        source_revision="revision-one",
        manifest_hash="manifest",
    )
    first_document = architecture_store.list_document_versions(first.id)[0]

    changed_text = (FIXTURES / "frontmatter-component.md").read_text(
        encoding="utf-8",
    ).replace("fixture is synthetic", "fixture remains synthetic")
    changed = parse_architecture_document(
        changed_text,
        "fixtures/demo/architecture/frontmatter-component.md",
    )
    second = architecture_store.activate(
        repository="Synthetic Architecture",
        documents=[changed],
        source_revision="revision-two",
        manifest_hash="manifest",
    )

    assert second.status == "active"
    assert architecture_store.get_snapshot(first.id).status == "historical"
    retained = architecture_store.get_document_version(first_document.id)
    assert retained is not None
    assert retained.body == first_document.body
    assert retained.content_hash == first_document.content_hash
    assert architecture_store.active_snapshot("synthetic architecture").id == second.id


def test_rejected_snapshot_does_not_replace_active_snapshot(
    architecture_store: ArchitectureStore,
):
    active = architecture_store.activate(
        repository="Synthetic Architecture",
        documents=[parsed_fixture("frontmatter-component.md")],
    )
    broken = parse_architecture_document(
        "# Missing declaration\n",
        "docs/missing.md",
    )
    rejected = architecture_store.activate(
        repository="Synthetic Architecture",
        documents=[broken],
        source_revision="broken",
    )

    assert rejected.status == "rejected"
    assert architecture_store.active_snapshot("Synthetic Architecture").id == active.id
    assert "missing_ai_card" in {
        issue.code for issue in architecture_store.list_issues(rejected.id)
    }
    assert "no_valid_architecture_cards" in {
        issue.code for issue in architecture_store.list_issues(rejected.id)
    }


def test_missing_card_is_a_visible_gap_when_valid_cards_exist(
    architecture_store: ArchitectureStore,
):
    missing = parse_architecture_document(
        "# Undocumented helper\n",
        "docs/undocumented.md",
    )
    snapshot = architecture_store.activate(
        repository="Synthetic Architecture",
        documents=[parsed_fixture("frontmatter-component.md"), missing],
    )
    assert snapshot.status == "active"
    assert snapshot.document_count == 2
    assert snapshot.valid_count == 1
    assert "missing_ai_card" in {
        issue.code for issue in architecture_store.list_issues(snapshot.id)
    }


def test_duplicate_stable_ids_are_rejected_without_constraint_failure(
    architecture_store: ArchitectureStore,
):
    first = parsed_fixture("frontmatter-component.md")
    duplicate = parse_architecture_document(
        (FIXTURES / "frontmatter-component.md").read_text(encoding="utf-8"),
        "docs/duplicate.md",
    )
    snapshot = architecture_store.activate(
        repository="Synthetic Architecture",
        documents=[first, duplicate],
    )
    assert snapshot.status == "rejected"
    assert "duplicate_stable_id" in {
        issue.code for issue in architecture_store.list_issues(snapshot.id)
    }


def test_transaction_rolls_back_when_document_insert_fails(
    architecture_store: ArchitectureStore,
    architecture_db: Database,
    monkeypatch,
):
    def fail(*_args, **_kwargs):
        raise RuntimeError("synthetic insert failure")

    monkeypatch.setattr(architecture_store, "_insert_document", fail)
    with pytest.raises(RuntimeError, match="synthetic insert failure"):
        architecture_store.activate(
            repository="Synthetic Architecture",
            documents=[parsed_fixture("frontmatter-component.md")],
            source_revision="rollback",
        )
    assert architecture_db.count("architecture_snapshots") == 0
