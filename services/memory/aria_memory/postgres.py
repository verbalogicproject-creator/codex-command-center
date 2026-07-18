from __future__ import annotations

import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .db import BASE_APP_MIGRATION_VERSION, Database
from .models import utc_now


POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_migrations(
  version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS memories(
  id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL DEFAULT 1,
  entity_type TEXT NOT NULL CHECK(entity_type IN ('episode','fact')),
  project TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
  title TEXT NOT NULL, content TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '',
  tags_json TEXT NOT NULL DEFAULT '[]', happened_at TEXT NOT NULL,
  created_at TEXT NOT NULL, supersedes_id TEXT REFERENCES memories(id));
CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project);
CREATE INDEX IF NOT EXISTS idx_memories_happened ON memories(happened_at DESC);
CREATE INDEX IF NOT EXISTS idx_active_facts ON memories(project,kind)
  WHERE entity_type='fact' AND status='active';
CREATE TABLE IF NOT EXISTS embeddings(
  memory_id TEXT PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
  content_hash TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
  dimensions INTEGER NOT NULL, vector BYTEA NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents(
  id TEXT PRIMARY KEY, source_uri TEXT NOT NULL UNIQUE,
  repository TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '',
  provides_json TEXT NOT NULL DEFAULT '[]',
  public_interfaces_json TEXT NOT NULL DEFAULT '[]',
  safe_edit_points_json TEXT NOT NULL DEFAULT '[]',
  risk_areas_json TEXT NOT NULL DEFAULT '[]',
  graph_rag_entities_json TEXT NOT NULL DEFAULT '[]',
  depends_on_json TEXT NOT NULL DEFAULT '[]',
  main_files_json TEXT NOT NULL DEFAULT '[]',
  kind TEXT NOT NULL DEFAULT 'ai-card', status TEXT NOT NULL DEFAULT 'active',
  owner_area TEXT NOT NULL DEFAULT '', audience TEXT NOT NULL DEFAULT '',
  last_verified TEXT, dimensions_json TEXT NOT NULL DEFAULT '{}',
  content_hash TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_documents_repository ON documents(repository,status);
CREATE TABLE IF NOT EXISTS document_embeddings(
  document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
  content_hash TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
  dimensions INTEGER NOT NULL, vector BYTEA NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(
  id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS turns(
  id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN ('user','assistant')), content TEXT NOT NULL,
  evidence_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id,created_at);
CREATE TABLE IF NOT EXISTS proposals(
  id TEXT PRIMARY KEY, session_id TEXT REFERENCES sessions(id) ON DELETE SET NULL,
  operation TEXT NOT NULL, payload_json TEXT NOT NULL, rationale TEXT NOT NULL,
  evidence_json TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT NOT NULL, resolved_at TEXT, memory_id TEXT REFERENCES memories(id), error TEXT);
CREATE TABLE IF NOT EXISTS audit_events(
  id TEXT PRIMARY KEY, action TEXT NOT NULL, actor TEXT NOT NULL,
  proposal_id TEXT, memory_id TEXT, detail_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS quota_events(
  id TEXT PRIMARY KEY, category TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_quota_category_time ON quota_events(category,created_at);
CREATE TABLE IF NOT EXISTS hook_events(
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, repository TEXT NOT NULL,
  session_id TEXT, tool_name TEXT, source_ids_json TEXT NOT NULL DEFAULT '[]',
  detail_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_hook_events_session ON hook_events(session_id,created_at);
CREATE TABLE IF NOT EXISTS capabilities(
  stable_id TEXT NOT NULL, version INTEGER NOT NULL,
  name TEXT NOT NULL, kind TEXT NOT NULL, description TEXT NOT NULL,
  triggers_json TEXT NOT NULL DEFAULT '[]', instructions TEXT NOT NULL,
  repositories_json TEXT NOT NULL DEFAULT '[]',
  required_tools_json TEXT NOT NULL DEFAULT '[]',
  trust_status TEXT NOT NULL, provenance TEXT NOT NULL,
  content_hash TEXT NOT NULL, verified_at TEXT NOT NULL, created_at TEXT NOT NULL,
  PRIMARY KEY(stable_id,version));
CREATE INDEX IF NOT EXISTS idx_capabilities_kind_trust
  ON capabilities(kind,trust_status);
CREATE TABLE IF NOT EXISTS handoffs(
  id TEXT PRIMARY KEY, lineage_id TEXT NOT NULL, version INTEGER NOT NULL,
  repository TEXT NOT NULL, original_request TEXT NOT NULL,
  screenshot_json TEXT, capability_refs_json TEXT NOT NULL DEFAULT '[]',
  open_plan_json TEXT NOT NULL DEFAULT '[]', architecture_json TEXT NOT NULL DEFAULT '{}',
  evidence_sources_json TEXT NOT NULL DEFAULT '[]',
  safe_edit_points_json TEXT NOT NULL DEFAULT '[]',
  risks_json TEXT NOT NULL DEFAULT '[]',
  tool_references_json TEXT NOT NULL DEFAULT '[]',
  token_estimate INTEGER NOT NULL, omitted_candidates INTEGER NOT NULL DEFAULT 0,
  degraded INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL CHECK(status IN ('draft','published','revoked')),
  creator TEXT NOT NULL, created_at TEXT NOT NULL, published_at TEXT, revoked_at TEXT,
  UNIQUE(lineage_id,version));
CREATE INDEX IF NOT EXISTS idx_handoffs_repository_status
  ON handoffs(repository,status,created_at DESC);
CREATE TABLE IF NOT EXISTS handoff_activations(
  id TEXT PRIMARY KEY, handoff_id TEXT NOT NULL REFERENCES handoffs(id),
  repository TEXT NOT NULL, client_name TEXT NOT NULL,
  session_id TEXT, evidence_ids_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workspace_tokens(
  id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL, created_at TEXT NOT NULL, revoked_at TEXT);
CREATE TABLE IF NOT EXISTS pair_codes(
  code_hash TEXT PRIMARY KEY, created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL, consumed_at TEXT);
"""

POSTGRES_ARCHITECTURE_MIGRATION_V5 = """
CREATE TABLE IF NOT EXISTS architecture_repositories(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  aliases_json TEXT NOT NULL DEFAULT '[]',
  manifest_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS architecture_snapshots(
  id TEXT PRIMARY KEY,
  repository_id TEXT NOT NULL REFERENCES architecture_repositories(id),
  repository TEXT NOT NULL,
  source_revision TEXT NOT NULL DEFAULT '',
  manifest_hash TEXT NOT NULL,
  corpus_hash TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('staging','active','historical','rejected')),
  document_count INTEGER NOT NULL DEFAULT 0,
  valid_count INTEGER NOT NULL DEFAULT 0,
  issue_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  activated_at TEXT,
  UNIQUE(repository_id,source_revision,manifest_hash,corpus_hash));
CREATE INDEX IF NOT EXISTS idx_architecture_snapshots_repository
  ON architecture_snapshots(repository_id,created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_architecture_active_repository
  ON architecture_snapshots(repository_id) WHERE status='active';
CREATE TABLE IF NOT EXISTS architecture_document_versions(
  id TEXT PRIMARY KEY,
  snapshot_id TEXT NOT NULL REFERENCES architecture_snapshots(id) ON DELETE CASCADE,
  stable_id TEXT NOT NULL,
  source_uri TEXT NOT NULL,
  dialect TEXT NOT NULL,
  title TEXT NOT NULL,
  declaration_json TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  content_hash TEXT NOT NULL,
  last_verified TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(snapshot_id,source_uri));
CREATE INDEX IF NOT EXISTS idx_architecture_documents_stable
  ON architecture_document_versions(snapshot_id,stable_id);
CREATE TABLE IF NOT EXISTS architecture_sections(
  id TEXT PRIMARY KEY,
  document_version_id TEXT NOT NULL
    REFERENCES architecture_document_versions(id) ON DELETE CASCADE,
  stable_id TEXT NOT NULL,
  heading TEXT NOT NULL,
  heading_slug TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  body TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  evidence_class TEXT NOT NULL DEFAULT 'derived',
  UNIQUE(document_version_id,ordinal));
CREATE INDEX IF NOT EXISTS idx_architecture_sections_document
  ON architecture_sections(document_version_id,ordinal);
CREATE TABLE IF NOT EXISTS architecture_section_embeddings(
  section_id TEXT PRIMARY KEY REFERENCES architecture_sections(id) ON DELETE CASCADE,
  content_hash TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  dimensions INTEGER NOT NULL,
  vector BYTEA NOT NULL,
  updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS architecture_edges(
  id TEXT PRIMARY KEY,
  snapshot_id TEXT NOT NULL REFERENCES architecture_snapshots(id) ON DELETE CASCADE,
  source_id TEXT NOT NULL,
  target_ref TEXT NOT NULL,
  target_id TEXT,
  relation_type TEXT NOT NULL,
  evidence_class TEXT NOT NULL,
  resolution_status TEXT NOT NULL
    CHECK(resolution_status IN ('resolved','unresolved','ambiguous')),
  source_document_version_id TEXT
    REFERENCES architecture_document_versions(id) ON DELETE CASCADE,
  source_field TEXT NOT NULL,
  created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_architecture_edges_source
  ON architecture_edges(snapshot_id,source_id,relation_type);
CREATE INDEX IF NOT EXISTS idx_architecture_edges_target
  ON architecture_edges(snapshot_id,target_id);
CREATE TABLE IF NOT EXISTS architecture_issues(
  id TEXT PRIMARY KEY,
  snapshot_id TEXT NOT NULL REFERENCES architecture_snapshots(id) ON DELETE CASCADE,
  source_uri TEXT NOT NULL,
  code TEXT NOT NULL,
  severity TEXT NOT NULL CHECK(severity IN ('info','warning','error')),
  detail_json TEXT NOT NULL DEFAULT '{}',
  evidence_class TEXT NOT NULL,
  created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_architecture_issues_snapshot
  ON architecture_issues(snapshot_id,severity,code);
"""

POSTGRES_APP_MIGRATIONS = {
    5: POSTGRES_ARCHITECTURE_MIGRATION_V5,
}


class CompatRow(dict[str, Any]):
    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return list(self.values())[key]
        value = super().__getitem__(key)
        return bytes(value) if isinstance(value, memoryview) else value


def compat_row_factory(cursor: Any):
    columns = [
        column.name for column in (cursor.description or ())
    ]

    def make_row(values: tuple[Any, ...]) -> CompatRow:
        return CompatRow(zip(columns, values, strict=True))

    return make_row


class CompatConnection:
    def __init__(self, raw: Any):
        self.raw = raw

    @staticmethod
    def _sql(query: str) -> str:
        return query.replace("?", "%s")

    def execute(self, query: str, params: Any = ()):
        return self.raw.execute(self._sql(query), params)

    def commit(self) -> None:
        self.raw.commit()

    def rollback(self) -> None:
        self.raw.rollback()

    def close(self) -> None:
        self.raw.close()

    def __enter__(self) -> "CompatConnection":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if exc_type:
            self.raw.rollback()
        else:
            self.raw.commit()
        self.raw.close()


class PostgresDatabase(Database):
    """Workspace-isolated PostgreSQL implementation of the SQLite contract."""

    dialect = "postgres"

    def __init__(self, url: str, workspace_id: str, seed_path: Path | None = None):
        if not re.fullmatch(r"ws_[0-9a-f]{16}", workspace_id):
            raise ValueError("invalid workspace schema identifier")
        self.url = url
        self.workspace_id = workspace_id
        self.path = Path(f"postgres/{workspace_id}")
        self.migrate()
        if self.count("memories") == 0 and seed_path and seed_path.exists():
            self.seed(seed_path)

    def _raw(self, search_path: bool = True):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "DATABASE_URL requires the psycopg production dependency"
            ) from exc
        raw = psycopg.connect(self.url, row_factory=compat_row_factory)
        if search_path:
            raw.execute(f'SET search_path TO "{self.workspace_id}"')
        return raw

    def connect(self) -> CompatConnection:
        return CompatConnection(self._raw())

    @contextmanager
    def transaction(self) -> Iterator[CompatConnection]:
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def migrate(self) -> None:
        raw = self._raw(search_path=False)
        try:
            raw.execute(f'CREATE SCHEMA IF NOT EXISTS "{self.workspace_id}"')
            raw.execute(f'SET search_path TO "{self.workspace_id}"')
            for statement in POSTGRES_SCHEMA.split(";"):
                if statement.strip():
                    raw.execute(statement)
            raw.execute(
                """INSERT INTO app_migrations(version,applied_at) VALUES(%s,%s)
                ON CONFLICT(version) DO NOTHING""",
                (BASE_APP_MIGRATION_VERSION, utc_now()),
            )
            applied = {
                int(row[0]) for row in raw.execute(
                    "SELECT version FROM app_migrations"
                ).fetchall()
            }
            for version, script in sorted(POSTGRES_APP_MIGRATIONS.items()):
                if version in applied:
                    continue
                for statement in script.split(";"):
                    if statement.strip():
                        raw.execute(statement)
                raw.execute(
                    "INSERT INTO app_migrations(version,applied_at) VALUES(%s,%s)",
                    (version, utc_now()),
                )
            raw.commit()
        except Exception:
            raw.rollback()
            raise
        finally:
            raw.close()
