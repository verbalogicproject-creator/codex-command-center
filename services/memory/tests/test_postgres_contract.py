from __future__ import annotations

import re

import pytest

from aria_memory.postgres import (
    CompatConnection,
    POSTGRES_APP_MIGRATIONS,
    POSTGRES_SCHEMA,
    PostgresDatabase,
)


EXPECTED_TABLES = {
    "app_migrations", "memories", "embeddings", "documents",
    "document_embeddings", "sessions", "turns", "proposals", "audit_events",
    "quota_events", "hook_events", "capabilities", "handoffs",
    "handoff_activations", "workspace_tokens", "pair_codes",
}
ARCHITECTURE_TABLES = {
    "architecture_repositories", "architecture_snapshots",
    "architecture_document_versions",
    "architecture_sections", "architecture_section_embeddings",
    "architecture_edges", "architecture_issues",
}


def test_postgres_schema_covers_mutable_workspace_contract():
    tables = set(re.findall(
        r"CREATE TABLE IF NOT EXISTS ([a-z_]+)", POSTGRES_SCHEMA,
        flags=re.IGNORECASE,
    ))
    assert tables == EXPECTED_TABLES
    assert "PRIMARY KEY(stable_id,version)" in POSTGRES_SCHEMA
    assert "UNIQUE(lineage_id,version)" in POSTGRES_SCHEMA
    assert "token_hash TEXT NOT NULL UNIQUE" in POSTGRES_SCHEMA
    assert "vector BYTEA NOT NULL" in POSTGRES_SCHEMA


def test_postgres_v5_schema_covers_versioned_architecture_contract():
    migration = POSTGRES_APP_MIGRATIONS[5]
    tables = set(re.findall(
        r"CREATE TABLE IF NOT EXISTS ([a-z_]+)", migration,
        flags=re.IGNORECASE,
    ))
    assert tables == ARCHITECTURE_TABLES
    assert "vector BYTEA NOT NULL" in migration
    assert "UNIQUE(snapshot_id,source_uri)" in migration
    assert "WHERE status='active'" in migration


def test_postgres_adapter_translates_portable_placeholders():
    assert CompatConnection._sql(
        "SELECT * FROM handoffs WHERE id=? AND status=?"
    ) == "SELECT * FROM handoffs WHERE id=%s AND status=%s"


def test_postgres_workspace_schema_identifier_is_strict():
    with pytest.raises(ValueError, match="invalid workspace"):
        PostgresDatabase("postgresql://unused", "public;drop", None)
