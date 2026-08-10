from __future__ import annotations

import json
import uuid
from typing import Any

from .db import Database
from .models import (
    AuditEvent, HookEventRequest, HookEventResponse, Proposal, Session, Turn, utc_now,
)


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class AppStore:
    def __init__(self, db: Database):
        self.db = db

    def create_session(self, title: str) -> Session:
        session_id, now = uid("ses"), utc_now()
        with self.db.transaction() as conn:
            conn.execute("INSERT INTO sessions VALUES(?,?,?,?)", (session_id, title, now, now))
        return Session(id=session_id, title=title, created_at=now, updated_at=now)

    def sessions(self) -> list[Session]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT s.*,COUNT(t.id) turn_count FROM sessions s
                LEFT JOIN turns t ON t.session_id=s.id GROUP BY s.id
                ORDER BY s.updated_at DESC"""
            ).fetchall()
        return [Session(**dict(row)) for row in rows]

    def session_exists(self, session_id: str) -> bool:
        with self.db.connect() as conn:
            return conn.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone() is not None

    def add_turn(
        self, session_id: str, role: str, content: str, evidence: list[str] | None = None,
        modality: str = "text", metadata: dict[str, Any] | None = None,
    ) -> None:
        now = utc_now()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO turns
                (id,session_id,role,content,evidence_json,created_at,modality,metadata_json)
                VALUES(?,?,?,?,?,?,?,?)""",
                (
                    uid("turn"), session_id, role, content, json.dumps(evidence or []),
                    now, modality, json.dumps(metadata or {}),
                ),
            )
            conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))

    def recent_turns(self, session_id: str, limit: int = 12) -> list[dict[str, str]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT role,content FROM (
                SELECT role,content,created_at FROM turns WHERE session_id=?
                ORDER BY created_at DESC LIMIT ?) ORDER BY created_at""",
                (session_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def visible_turns(self, session_id: str, limit: int = 100) -> list[Turn]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT id,role,content,evidence_json,created_at,modality,metadata_json FROM turns
                WHERE session_id=? ORDER BY created_at LIMIT ?""",
                (session_id, limit),
            ).fetchall()
        return [Turn(
            id=row["id"], role=row["role"], content=row["content"],
            evidence_ids=json.loads(row["evidence_json"]), created_at=row["created_at"],
            modality=row["modality"], metadata=json.loads(row["metadata_json"]),
        ) for row in rows]

    def create_proposal(
        self, session_id: str | None, operation: str, payload: dict[str, Any],
        rationale: str, evidence_ids: list[str],
    ) -> Proposal:
        proposal_id, now = uid("prop"), utc_now()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO proposals(id,session_id,operation,payload_json,rationale,
                evidence_json,status,created_at) VALUES(?,?,?,?,?,?,'pending',?)""",
                (proposal_id, session_id, operation, json.dumps(payload), rationale,
                 json.dumps(evidence_ids), now),
            )
            self._audit(conn, "proposal.created", "aria", proposal_id, None, {"operation": operation})
        return self.get_proposal(proposal_id)  # type: ignore[return-value]

    @staticmethod
    def proposal_from_row(row: Any) -> Proposal:
        return Proposal(
            id=row["id"], session_id=row["session_id"], operation=row["operation"],
            payload=json.loads(row["payload_json"]), rationale=row["rationale"],
            evidence_ids=json.loads(row["evidence_json"]), status=row["status"],
            created_at=row["created_at"], resolved_at=row["resolved_at"],
            memory_id=row["memory_id"], error=row["error"],
        )

    def get_proposal(self, proposal_id: str) -> Proposal | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
        return self.proposal_from_row(row) if row else None

    def proposals(
        self, session_id: str | None = None, status: str | None = None, limit: int = 100,
    ) -> list[Proposal]:
        sql = "SELECT * FROM proposals"
        clauses: list[str] = []
        args: list[Any] = []
        if session_id is not None:
            clauses.append("session_id=?")
            args.append(session_id)
        if status is not None:
            clauses.append("status=?")
            args.append(status)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        with self.db.connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [self.proposal_from_row(row) for row in rows]

    def record_hook(self, event: HookEventRequest) -> HookEventResponse:
        """Store bounded telemetry; raw prompts/tool output are never accepted."""
        event_id, now = uid("hook"), utc_now()
        allowed_detail = {
            key: value for key, value in event.detail.items()
            if key in {
                "summary", "outcome", "changed_files", "duration_ms", "exit_code",
                "draft_proposal",
            }
        }
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO hook_events VALUES(?,?,?,?,?,?,?,?)""",
                (event_id, event.kind, event.repository, event.session_id,
                 event.tool_name, json.dumps(event.source_ids),
                 json.dumps(allowed_detail), now),
            )
        proposal = None
        if event.kind == "stop" and allowed_detail.get("draft_proposal") is True:
            summary = str(allowed_detail.get("summary") or "Codex session completed.")
            session_id = (
                event.session_id
                if event.session_id and self.session_exists(event.session_id) else None
            )
            proposal = self.create_proposal(
                session_id,
                "remember_episode",
                {
                    "project": event.repository,
                    "kind": "coding-session",
                    "title": "Codex session summary",
                    "content": summary[:2_000],
                    "reason": "Drafted by the Stop hook for browser review",
                    "tags": ["codex", "session", "proposed"],
                },
                "Review this sanitized session summary before making it durable.",
                event.source_ids[:20],
            )
        return HookEventResponse(id=event_id, kind=event.kind, proposal=proposal)

    @staticmethod
    def _audit(conn: Any, action: str, actor: str, proposal_id: str | None,
               memory_id: str | None, detail: dict[str, Any]) -> None:
        conn.execute(
            "INSERT INTO audit_events VALUES(?,?,?,?,?,?,?)",
            (uid("audit"), action, actor, proposal_id, memory_id, json.dumps(detail), utc_now()),
        )

    def confirm(self, proposal_id: str) -> Proposal:
        try:
            return self._confirm_once(proposal_id)
        except ValueError as exc:
            with self.db.transaction() as conn:
                row = conn.execute(
                    "SELECT status,operation FROM proposals WHERE id=?", (proposal_id,)
                ).fetchone()
                if row and row["status"] == "pending":
                    conn.execute(
                        """UPDATE proposals SET status='failed',resolved_at=?,error=?
                        WHERE id=?""", (utc_now(), str(exc), proposal_id),
                    )
                    self._audit(conn, "proposal.failed", "system", proposal_id, None,
                                {"operation": row["operation"], "error": str(exc)})
            raise

    def _confirm_once(self, proposal_id: str) -> Proposal:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
            if not row:
                raise KeyError("proposal not found")
            proposal = self.proposal_from_row(row)
            if proposal.status == "confirmed":
                return proposal
            if proposal.status != "pending":
                raise ValueError(f"proposal is {proposal.status}")
            payload = dict(proposal.payload)
            operation = proposal.operation
            if operation == "invalidate_fact":
                target = payload.get("target_id")
                changed = conn.execute(
                    "UPDATE memories SET status='inactive' WHERE id=? AND entity_type='fact'",
                    (target,),
                ).rowcount
                if not changed:
                    raise ValueError("active fact target not found")
                memory_id = target
            else:
                claim = f"{payload.get('title', '')} {payload.get('content', '')}".lower()
                if "merge" in claim:
                    boundaries = conn.execute(
                        """SELECT id,content FROM memories WHERE kind='decision' AND status='active'
                        AND (lower(content) LIKE '%not merge%'
                          OR lower(content) LIKE '%will not merge%'
                          OR lower(content) LIKE '%not as a merged%')"""
                    ).fetchall()
                    if boundaries:
                        raise ValueError(
                            "MUD guard: proposed synthesis conflicts with "
                            + ", ".join(row["id"] for row in boundaries)
                        )
                if operation == "supersede_fact":
                    target = payload.get("target_id")
                    old = conn.execute(
                        "SELECT * FROM memories WHERE id=? AND entity_type='fact' AND status='active'",
                        (target,),
                    ).fetchone()
                    if not old:
                        raise ValueError("active fact target not found")
                    conn.execute("UPDATE memories SET status='superseded' WHERE id=?", (target,))
                    payload["entity_type"] = "fact"
                    payload["supersedes_id"] = target
                elif operation == "remember_episode":
                    payload["entity_type"] = "episode"
                else:
                    payload["entity_type"] = "fact"
                required = ("project", "title", "content")
                if any(not str(payload.get(key, "")).strip() for key in required):
                    raise ValueError("project, title and content are required")
                memory_id = Database.insert_memory(conn, payload)
            now = utc_now()
            conn.execute(
                """UPDATE proposals SET status='confirmed',resolved_at=?,memory_id=?
                WHERE id=?""", (now, memory_id, proposal_id),
            )
            self._audit(conn, "proposal.confirmed", "human", proposal_id, memory_id,
                        {"operation": operation})
        return self.get_proposal(proposal_id)  # type: ignore[return-value]

    def reject(self, proposal_id: str) -> Proposal:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
            if not row:
                raise KeyError("proposal not found")
            proposal = self.proposal_from_row(row)
            if proposal.status == "rejected":
                return proposal
            if proposal.status != "pending":
                raise ValueError(f"proposal is {proposal.status}")
            conn.execute(
                "UPDATE proposals SET status='rejected',resolved_at=? WHERE id=?",
                (utc_now(), proposal_id),
            )
            self._audit(conn, "proposal.rejected", "human", proposal_id, None,
                        {"operation": proposal.operation})
        return self.get_proposal(proposal_id)  # type: ignore[return-value]

    def audit(self, limit: int = 100) -> list[AuditEvent]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_events ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [AuditEvent(
            id=r["id"], action=r["action"], actor=r["actor"],
            proposal_id=r["proposal_id"], memory_id=r["memory_id"],
            detail=json.loads(r["detail_json"]), created_at=r["created_at"],
        ) for r in rows]
