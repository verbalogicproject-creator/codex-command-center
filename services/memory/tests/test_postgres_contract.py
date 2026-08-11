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


def test_postgres_v6_adds_persisted_handoff_planning_receipt():
    migration = POSTGRES_APP_MIGRATIONS[6]
    assert "ALTER TABLE handoffs" in migration
    assert "planning_receipt_json TEXT NOT NULL" in migration


def test_postgres_v7_adds_role_labelled_visual_comparison_receipt():
    migration = POSTGRES_APP_MIGRATIONS[7]
    assert "ALTER TABLE handoffs" in migration
    assert "visual_brief_json TEXT NOT NULL" in migration


def test_postgres_v8_matches_aria_command_center_contract():
    migration = POSTGRES_APP_MIGRATIONS[8]
    tables = set(re.findall(
        r"CREATE TABLE IF NOT EXISTS ([a-z_]+)", migration,
        flags=re.IGNORECASE,
    ))
    assert tables == {
        "aria_command_definitions", "aria_profiles", "aria_command_aliases",
        "aria_voice_sessions", "aria_command_executions",
    }
    assert "ADD COLUMN IF NOT EXISTS modality" in migration
    assert "profile_snapshot_json TEXT NOT NULL" in migration
    assert "UNIQUE(voice_session_id,call_id)" in migration


def test_postgres_v9_adds_multi_project_handoff_and_session_contract():
    migration = POSTGRES_APP_MIGRATIONS[9]
    assert "source_repositories_json TEXT NOT NULL" in migration
    assert "selected_evidence_ids_json TEXT NOT NULL" in migration
    assert "composition_json TEXT NOT NULL" in migration
    assert "ALTER TABLE sessions" in migration
    assert "repository,status,updated_at DESC" in migration


def test_postgres_adapter_translates_portable_placeholders():
    assert CompatConnection._sql(
        "SELECT * FROM handoffs WHERE id=? AND status=?"
    ) == "SELECT * FROM handoffs WHERE id=%s AND status=%s"
    assert CompatConnection._sql(
        "SELECT 1 WHERE payload LIKE '%' || ? || '%'"
    ) == "SELECT 1 WHERE payload LIKE '%%' || %s || '%%'"


def test_postgres_workspace_schema_identifier_is_strict():
    with pytest.raises(ValueError, match="invalid workspace"):
        PostgresDatabase("postgresql://unused", "public;drop", None)
