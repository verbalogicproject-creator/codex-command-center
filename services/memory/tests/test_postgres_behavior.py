from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from aria_memory.architecture import (
    ArchitectureBriefRequest,
    ArchitectureCompiler,
    ArchitectureStore,
    parse_architecture_document,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = (
    ROOT / "fixtures" / "demo" / "architecture" / "frontmatter-component.md"
)


@pytest.mark.skipif(
    not os.getenv("COMMAND_CENTER_TEST_DATABASE_URL"),
    reason="COMMAND_CENTER_TEST_DATABASE_URL is not configured",
)
def test_postgres_snapshot_activation_restart_and_historical_evidence():
    from aria_memory.postgres import PostgresDatabase

    url = os.environ["COMMAND_CENTER_TEST_DATABASE_URL"]
    workspace_id = f"ws_{uuid.uuid4().hex[:16]}"
    db = PostgresDatabase(url, workspace_id)
    try:
        store = ArchitectureStore(db)
        source = FIXTURE.read_text(encoding="utf-8")
        first = store.activate(
            repository="Synthetic Architecture",
            repository_id="synthetic-architecture",
            aliases=["synthetic-checkout"],
            documents=[parse_architecture_document(
                source,
                "docs/architecture.md",
                repository="Synthetic Architecture",
            )],
            source_revision="postgres-revision-one",
            manifest_hash="a" * 64,
        )
        first_document = store.list_document_versions(first.id)[0]
        second = store.activate(
            repository="Synthetic Architecture",
            repository_id="synthetic-architecture",
            aliases=["synthetic-checkout"],
            documents=[parse_architecture_document(
                source.replace(
                    "The fixture is synthetic",
                    "The PostgreSQL fixture is synthetic",
                ),
                "docs/architecture.md",
                repository="Synthetic Architecture",
            )],
            source_revision="postgres-revision-two",
            manifest_hash="b" * 64,
        )
        assert first.id != second.id
        assert store.get_snapshot(first.id).status == "historical"
        assert store.get_document_version(first_document.id).body == first_document.body

        restarted_store = ArchitectureStore(PostgresDatabase(url, workspace_id))
        brief = ArchitectureCompiler(restarted_store).build(
            ArchitectureBriefRequest(
                repository="synthetic-checkout",
                mode="task",
                prompt="frontmatter contract",
                token_budget=1_200,
            )
        )
        assert brief.snapshot_receipt["snapshot_id"] == second.id
        assert brief.snapshot_receipt["source_revision"] == "postgres-revision-two"
        assert brief.documents
        assert brief.sources
        assert brief.token_estimate <= brief.token_budget
    finally:
        raw = db._raw(search_path=False)
        try:
            raw.execute(f'DROP SCHEMA IF EXISTS "{workspace_id}" CASCADE')
            raw.commit()
        finally:
            raw.close()
