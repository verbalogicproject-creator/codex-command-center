from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .models import MemoryRecord, utc_now

SCHEMA_VERSION = 1
APP_MIGRATION_VERSION = 1


class Database:
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
                """
            )
            conn.execute(
                "INSERT OR IGNORE INTO app_migrations VALUES (?,?)",
                (APP_MIGRATION_VERSION, utc_now()),
            )

    def count(self, table: str) -> int:
        if table not in {"memories", "sessions", "proposals", "embeddings", "audit_events"}:
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
