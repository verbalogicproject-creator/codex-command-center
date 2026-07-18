from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .models import MemoryRecord, utc_now

SCHEMA_VERSION = 1
BASE_APP_MIGRATION_VERSION = 4
APP_MIGRATION_VERSION = 5

SQLITE_ARCHITECTURE_MIGRATION_V5 = """
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
  vector BLOB NOT NULL,
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

SQLITE_APP_MIGRATIONS = {
    5: SQLITE_ARCHITECTURE_MIGRATION_V5,
}


def execute_statements(conn: Any, script: str) -> None:
    for statement in script.split(";"):
        if statement.strip():
            conn.execute(statement)


class Database:
    dialect = "sqlite"
    def __init__(self, path: Path, seed_path: Path | None = None):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()
        if self.count("memories") == 0 and seed_path and seed_path.exists():
            self.seed(seed_path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=20, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def migrate(self) -> None:
        with self.transaction() as conn:
            conn.executescript(
                """
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
                  dimensions INTEGER NOT NULL, vector BLOB NOT NULL, updated_at TEXT NOT NULL);
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
                CREATE INDEX IF NOT EXISTS idx_documents_repository
                  ON documents(repository,status);
                CREATE TABLE IF NOT EXISTS document_embeddings(
                  document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
                  content_hash TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
                  dimensions INTEGER NOT NULL, vector BLOB NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions(
                  id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS turns(
                  id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                  role TEXT NOT NULL CHECK(role IN ('user','assistant')), content TEXT NOT NULL,
                  evidence_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id,created_at);
                CREATE TABLE IF NOT EXISTS proposals(
                  id TEXT PRIMARY KEY, session_id TEXT REFERENCES sessions(id) ON DELETE SET NULL,
                  operation TEXT NOT NULL, payload_json TEXT NOT NULL, rationale TEXT NOT NULL,
                  evidence_json TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'pending',
                  created_at TEXT NOT NULL, resolved_at TEXT, memory_id TEXT REFERENCES memories(id),
                  error TEXT);
                CREATE TABLE IF NOT EXISTS audit_events(
                  id TEXT PRIMARY KEY, action TEXT NOT NULL, actor TEXT NOT NULL,
                  proposal_id TEXT, memory_id TEXT, detail_json TEXT NOT NULL DEFAULT '{}',
                  created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS quota_events(
                  id TEXT PRIMARY KEY, category TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_quota_category_time
                  ON quota_events(category,created_at);
                CREATE TABLE IF NOT EXISTS hook_events(
                  id TEXT PRIMARY KEY, kind TEXT NOT NULL, repository TEXT NOT NULL,
                  session_id TEXT, tool_name TEXT, source_ids_json TEXT NOT NULL DEFAULT '[]',
                  detail_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_hook_events_session
                  ON hook_events(session_id,created_at);
                CREATE TABLE IF NOT EXISTS capabilities(
                  stable_id TEXT NOT NULL, version INTEGER NOT NULL,
                  name TEXT NOT NULL, kind TEXT NOT NULL, description TEXT NOT NULL,
                  triggers_json TEXT NOT NULL DEFAULT '[]',
                  instructions TEXT NOT NULL,
                  repositories_json TEXT NOT NULL DEFAULT '[]',
                  required_tools_json TEXT NOT NULL DEFAULT '[]',
                  trust_status TEXT NOT NULL, provenance TEXT NOT NULL,
                  content_hash TEXT NOT NULL, verified_at TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  PRIMARY KEY(stable_id,version));
                CREATE INDEX IF NOT EXISTS idx_capabilities_kind_trust
                  ON capabilities(kind,trust_status);
                CREATE TABLE IF NOT EXISTS handoffs(
                  id TEXT PRIMARY KEY, lineage_id TEXT NOT NULL, version INTEGER NOT NULL,
                  repository TEXT NOT NULL, original_request TEXT NOT NULL,
                  screenshot_json TEXT, capability_refs_json TEXT NOT NULL DEFAULT '[]',
                  open_plan_json TEXT NOT NULL DEFAULT '[]',
                  architecture_json TEXT NOT NULL DEFAULT '{}',
                  evidence_sources_json TEXT NOT NULL DEFAULT '[]',
                  safe_edit_points_json TEXT NOT NULL DEFAULT '[]',
                  risks_json TEXT NOT NULL DEFAULT '[]',
                  tool_references_json TEXT NOT NULL DEFAULT '[]',
                  token_estimate INTEGER NOT NULL, omitted_candidates INTEGER NOT NULL DEFAULT 0,
                  degraded INTEGER NOT NULL DEFAULT 0,
                  status TEXT NOT NULL CHECK(status IN ('draft','published','revoked')),
                  creator TEXT NOT NULL, created_at TEXT NOT NULL,
                  published_at TEXT, revoked_at TEXT,
                  UNIQUE(lineage_id,version));
                CREATE INDEX IF NOT EXISTS idx_handoffs_repository_status
                  ON handoffs(repository,status,created_at DESC);
                CREATE TABLE IF NOT EXISTS handoff_activations(
                  id TEXT PRIMARY KEY, handoff_id TEXT NOT NULL REFERENCES handoffs(id),
                  repository TEXT NOT NULL, client_name TEXT NOT NULL,
                  session_id TEXT, evidence_ids_json TEXT NOT NULL DEFAULT '[]',
                  created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS workspace_tokens(
                  id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE,
                  label TEXT NOT NULL, created_at TEXT NOT NULL, revoked_at TEXT);
                CREATE TABLE IF NOT EXISTS pair_codes(
                  code_hash TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL, consumed_at TEXT);
                """
            )
            conn.execute(
                "INSERT OR IGNORE INTO app_migrations VALUES (?,?)",
                (BASE_APP_MIGRATION_VERSION, utc_now()),
            )
            applied = {
                int(row[0]) for row in conn.execute(
                    "SELECT version FROM app_migrations"
                ).fetchall()
            }
            for version, script in sorted(SQLITE_APP_MIGRATIONS.items()):
                if version in applied:
                    continue
                execute_statements(conn, script)
                conn.execute(
                    "INSERT INTO app_migrations VALUES (?,?)",
                    (version, utc_now()),
                )

    def count(self, table: str) -> int:
        if table not in {
            "memories", "documents", "sessions", "proposals", "embeddings",
            "document_embeddings", "audit_events", "hook_events",
            "capabilities", "handoffs", "handoff_activations", "workspace_tokens",
            "pair_codes", "architecture_snapshots",
            "architecture_repositories",
            "architecture_document_versions", "architecture_sections",
            "architecture_section_embeddings", "architecture_edges",
            "architecture_issues",
        }:
            raise ValueError("unknown table")
        with self.connect() as conn:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def seed(self, path: Path) -> None:
        with self.transaction() as conn:
            for item in json.loads(path.read_text()):
                self.insert_memory(conn, item)

    @staticmethod
    def insert_memory(conn: sqlite3.Connection, item: dict[str, Any]) -> str:
        memory_id = item.get("id") or f"mem_{uuid.uuid4().hex[:16]}"
        now = utc_now()
        conn.execute(
            """INSERT INTO memories(id,schema_version,entity_type,project,kind,status,title,
            content,reason,tags_json,happened_at,created_at,supersedes_id)
            VALUES (?,1,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                memory_id, item["entity_type"], item["project"], item.get("kind", "note"),
                item.get("status", "active"), item["title"], item["content"],
                item.get("reason", ""), json.dumps(item.get("tags", [])),
                item.get("happened_at", now), item.get("created_at", now),
                item.get("supersedes_id"),
            ),
        )
        return memory_id

    @staticmethod
    def row_to_memory(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=row["id"], entity_type=row["entity_type"], project=row["project"],
            kind=row["kind"], status=row["status"], title=row["title"],
            content=row["content"], reason=row["reason"], tags=json.loads(row["tags_json"]),
            happened_at=row["happened_at"], created_at=row["created_at"],
            supersedes_id=row["supersedes_id"],
        )

    def get_memory(self, memory_id: str) -> MemoryRecord | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
        return self.row_to_memory(row) if row else None

    def list_memories(
        self, project: str | None = None, kinds: list[str] | None = None
    ) -> list[MemoryRecord]:
        clauses = ["NOT (entity_type='fact' AND status='inactive')"]
        args: list[Any] = []
        if project:
            clauses.append("project=?")
            args.append(project)
        if kinds:
            clauses.append("kind IN (%s)" % ",".join("?" for _ in kinds))
            args.extend(kinds)
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE " + " AND ".join(clauses), args
            ).fetchall()
        return [self.row_to_memory(row) for row in rows]
