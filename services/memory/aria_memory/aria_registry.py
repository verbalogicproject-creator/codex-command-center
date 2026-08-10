from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any

from .db import Database
from .models import utc_now

RESERVED_PHRASES = {"approve this handoff"}
VOICES = {"alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse"}
PRESETS = {"balanced", "concise", "coach", "architect"}
GLOBAL_COMMANDS = {
    "navigate_surface", "scroll_page", "scroll_to", "start_guided_tour",
    "tour_next", "tour_back", "tour_repeat", "tour_stop",
}


def _schema(properties: dict[str, Any] | None = None, required: list[str] | None = None):
    return {
        "type": "object",
        "properties": properties or {},
        "required": required or [],
        "additionalProperties": False,
    }


def _command(
    name: str,
    description: str,
    scopes: list[str],
    properties: dict[str, Any] | None = None,
    required: list[str] | None = None,
    safety: str = "standard",
    confirmation: str = "none",
    eligible: bool = True,
) -> dict[str, Any]:
    return {
        "id": name,
        "version": 1,
        "name": name,
        "description": description,
        "tool_schema": _schema(properties, required),
        "handler_key": name,
        "scopes": scopes,
        "safety_class": safety,
        "confirmation_policy": confirmation,
        "eligible": eligible,
        "release_status": "active",
    }


COMMAND_MANIFEST = [
    _command("navigate_surface", "Open a Command Center surface.", ["global"], {
        "surface": {"type": "string", "enum": [
            "aria", "handoff", "capabilities", "recall", "graph", "timeline", "audit",
        ]},
    }, ["surface"]),
    _command("scroll_page", "Scroll the current surface.", ["global"], {
        "direction": {"type": "string", "enum": ["up", "down", "top", "bottom"]},
        "amount": {"type": "string", "enum": ["small", "page"]},
    }, ["direction"]),
    _command("scroll_to", "Move to a named region.", ["global"], {
        "target": {"type": "string", "enum": ["heading", "content", "composer", "results"]},
    }, ["target"]),
    _command("open_evidence", "Open a cited evidence source.", ["aria", "recall", "graph"], {
        "source_id": {"type": "string"},
    }, ["source_id"]),
    _command("close_evidence", "Close the evidence drawer.", ["aria", "recall", "graph"]),
    _command("focus_graph_node", "Center a graph evidence node.", ["graph"], {
        "source_id": {"type": "string"},
    }, ["source_id"]),
    _command("fit_graph", "Fit active or all graph nodes.", ["graph"], {
        "mode": {"type": "string", "enum": ["active", "all"]},
    }, ["mode"]),
    _command("select_session", "Select a visible Aria session.", ["aria", "timeline"], {
        "session_id": {"type": "string"},
    }, ["session_id"]),
    _command("run_recall", "Run bounded evidence recall.", ["recall"], {
        "query": {"type": "string"},
    }, ["query"]),
    _command("set_deep_synthesis", "Change synthesis depth.", ["aria"], {
        "enabled": {"type": "boolean"},
    }, ["enabled"]),
    _command("open_context_packet", "Open the latest context packet.", ["aria"]),
    _command("start_guided_tour", "Start a guided tour.", ["global"], {
        "mode": {"type": "string", "enum": ["overview", "redesign"]},
    }),
    _command("tour_next", "Advance the tour.", ["global"]),
    _command("tour_back", "Go back in the tour.", ["global"]),
    _command("tour_repeat", "Repeat the tour step.", ["global"]),
    _command("tour_stop", "Stop the tour.", ["global"]),
    _command("draft_memory_proposal", "Create a pending memory proposal.", ["aria"], {
        "title": {"type": "string"}, "content": {"type": "string"},
        "rationale": {"type": "string"},
    }, ["title", "content", "rationale"], safety="protected",
        confirmation="human_tap"),
    _command("start_redesign_session", "Prefill Handoff Builder.", ["handoff"], {
        "repository": {"type": "string"}, "intent": {"type": "string"},
        "target_surface": {"type": "string"},
    }, ["repository", "intent"]),
    _command("prepare_redesign_handoff", "Prepare a draft from uploaded screenshots.", ["handoff"]),
    _command("select_handoff_capability", "Select a visible trusted capability.", ["handoff"], {
        "capability_ref": {"type": "string"},
    }, ["capability_ref"], safety="protected"),
    _command("edit_open_plan", "Edit the reversible visible plan.", ["handoff"], {
        "operation": {"type": "string", "enum": ["append", "replace", "remove", "reorder"]},
        "index": {"type": "integer"}, "text": {"type": "string"},
        "destination": {"type": "integer"},
    }, ["operation", "index"]),
    _command("open_handoff_packet", "Open the visible bounded handoff packet.", ["handoff"]),
    _command("approve_handoff", "Publish only after the exact protected phrase.", ["handoff"], {
        "confirmation_phrase": {"type": "string"},
    }, ["confirmation_phrase"], safety="protected", confirmation="exact_phrase"),
    _command("confirm_memory_write", "Durable memory confirmation is tap-only.", ["aria"],
        safety="human_only", confirmation="human_tap", eligible=False),
    _command("upload_screenshot", "Screenshot upload requires browser file permission.", ["handoff"],
        safety="browser_permission", confirmation="browser_permission", eligible=False),
    _command("deploy_code", "Aria cannot deploy or edit code.", ["handoff"],
        safety="ineligible", confirmation="forbidden", eligible=False),
]


def source_hash(item: dict[str, Any]) -> str:
    payload = json.dumps(item, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def normalize_alias(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def bounded(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return "[truncated]"
    if isinstance(value, str):
        lowered = value.casefold()
        if any(marker in lowered for marker in ("api_key", "authorization", "secret", "audio/")):
            return "[redacted]"
        return value[:2_000]
    if isinstance(value, dict):
        return {
            str(key)[:80]: bounded(item, depth=depth + 1)
            for key, item in list(value.items())[:40]
            if str(key).casefold() not in {
                "audio", "sdp", "webrtc", "api_key", "authorization", "credential",
            }
        }
    if isinstance(value, list):
        return [bounded(item, depth=depth + 1) for item in value[:40]]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:500]


class AriaRegistry:
    def __init__(self, db: Database):
        self.db = db
        self.reconcile()

    def reconcile(self) -> None:
        now = utc_now()
        enabled = [item["id"] for item in COMMAND_MANIFEST if item["eligible"]]
        with self.db.transaction() as conn:
            for item in COMMAND_MANIFEST:
                values = (
                    item["id"], item["version"], item["name"], item["description"],
                    json.dumps(item["tool_schema"], separators=(",", ":")),
                    item["handler_key"], json.dumps(item["scopes"]),
                    item["safety_class"], item["confirmation_policy"],
                    int(item["eligible"]), source_hash(item), item["release_status"], now,
                )
                conn.execute(
                    """INSERT INTO aria_command_definitions
                    (id,version,name,description,tool_schema_json,handler_key,scopes_json,
                    safety_class,confirmation_policy,eligible,source_hash,release_status,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                    version=excluded.version,name=excluded.name,description=excluded.description,
                    tool_schema_json=excluded.tool_schema_json,handler_key=excluded.handler_key,
                    scopes_json=excluded.scopes_json,safety_class=excluded.safety_class,
                    confirmation_policy=excluded.confirmation_policy,eligible=excluded.eligible,
                    source_hash=excluded.source_hash,release_status=excluded.release_status,
                    updated_at=excluded.updated_at""",
                    values,
                )
            default = conn.execute(
                "SELECT id FROM aria_profiles WHERE is_default=1"
            ).fetchone()
            if not default:
                conn.execute(
                    """INSERT INTO aria_profiles VALUES
                    (?,?,?,?,?,?,?,?,?,1,?,?)""",
                    (
                        "profile_default", "Default", "coral", "balanced",
                        50, 65, 40, 45, json.dumps(enabled), now, now,
                    ),
                )

    @staticmethod
    def command_from_row(row: Any) -> dict[str, Any]:
        return {
            "id": row["id"], "version": row["version"], "name": row["name"],
            "description": row["description"],
            "tool_schema": json.loads(row["tool_schema_json"]),
            "handler_key": row["handler_key"], "scopes": json.loads(row["scopes_json"]),
            "safety_class": row["safety_class"],
            "confirmation_policy": row["confirmation_policy"],
            "eligible": bool(row["eligible"]), "source_hash": row["source_hash"],
            "release_status": row["release_status"],
        }

    def commands(
        self, surface: str | None = None, workflow: str | None = None,
        profile_id: str = "profile_default",
    ) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM aria_command_definitions WHERE release_status='active' ORDER BY id"
            ).fetchall()
            profile = conn.execute(
                "SELECT enabled_command_ids_json FROM aria_profiles WHERE id=?",
                (profile_id,),
            ).fetchone()
            aliases = conn.execute(
                "SELECT command_id,alias FROM aria_command_aliases WHERE profile_id=?",
                (profile_id,),
            ).fetchall()
        enabled = set(json.loads(profile["enabled_command_ids_json"])) if profile else set()
        alias_map: dict[str, list[str]] = {}
        for alias in aliases:
            alias_map.setdefault(alias["command_id"], []).append(alias["alias"])
        projected = []
        for row in rows:
            item = self.command_from_row(row)
            scopes = set(item["scopes"])
            in_scope = (
                item["id"] in GLOBAL_COMMANDS
                or surface is None
                or surface in scopes
                or (workflow is not None and workflow in scopes)
            )
            if in_scope and (not item["eligible"] or item["id"] in enabled):
                item["aliases"] = alias_map.get(item["id"], [])
                projected.append(item)
        return projected

    @staticmethod
    def profile_from_row(row: Any) -> dict[str, Any]:
        return {
            "id": row["id"], "name": row["name"], "voice": row["voice"],
            "preset": row["preset"], "tone": row["tone"],
            "directness": row["directness"], "verbosity": row["verbosity"],
            "initiative": row["initiative"],
            "enabled_command_ids": json.loads(row["enabled_command_ids_json"]),
            "is_default": bool(row["is_default"]), "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def profiles(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM aria_profiles ORDER BY is_default DESC,name"
            ).fetchall()
        return [self.profile_from_row(row) for row in rows]

    def profile(self, profile_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM aria_profiles WHERE id=?", (profile_id,)
            ).fetchone()
        return self.profile_from_row(row) if row else None

    def save_profile(self, data: dict[str, Any], profile_id: str | None = None):
        voice, preset = data.get("voice", "coral"), data.get("preset", "balanced")
        if voice not in VOICES or preset not in PRESETS:
            raise ValueError("unknown voice or persona preset")
        profile_id = profile_id or f"profile_{uuid.uuid4().hex[:16]}"
        existing = self.profile(profile_id)
        if existing and existing["is_default"] and data.get("name") != "Default":
            raise PermissionError("the default profile cannot be renamed")
        commands = set(data.get("enabled_command_ids", []))
        eligible = {item["id"] for item in COMMAND_MANIFEST if item["eligible"]}
        if not commands <= eligible:
            raise ValueError("profile contains protected or unknown commands")
        dials = [int(data.get(key, 50)) for key in (
            "tone", "directness", "verbosity", "initiative",
        )]
        if any(value < 0 or value > 100 for value in dials):
            raise ValueError("persona dials must be between 0 and 100")
        now = utc_now()
        created = existing["created_at"] if existing else now
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO aria_profiles
                (id,name,voice,preset,tone,directness,verbosity,initiative,
                enabled_command_ids_json,is_default,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name,voice=excluded.voice,
                preset=excluded.preset,tone=excluded.tone,directness=excluded.directness,
                verbosity=excluded.verbosity,initiative=excluded.initiative,
                enabled_command_ids_json=excluded.enabled_command_ids_json,
                updated_at=excluded.updated_at""",
                (
                    profile_id, str(data.get("name", "Workspace profile"))[:80],
                    voice, preset, *dials, json.dumps(sorted(commands)),
                    int(existing["is_default"]) if existing else 0, created, now,
                ),
            )
        return self.profile(profile_id)

    def add_alias(self, profile_id: str, command_id: str, alias: str):
        normalized = normalize_alias(alias)
        if not normalized or normalized in RESERVED_PHRASES:
            raise ValueError("alias is empty or reserved")
        if not any(item["id"] == command_id and item["eligible"] for item in COMMAND_MANIFEST):
            raise ValueError("aliases require a voice-eligible command")
        alias_id = f"alias_{uuid.uuid4().hex[:16]}"
        try:
            with self.db.transaction() as conn:
                conn.execute(
                    "INSERT INTO aria_command_aliases VALUES(?,?,?,?,?,?)",
                    (alias_id, profile_id, command_id, alias[:120], normalized, utc_now()),
                )
        except Exception as exc:
            raise ValueError("alias collides with an existing spoken alias") from exc
        return {"id": alias_id, "profile_id": profile_id, "command_id": command_id,
                "alias": alias[:120], "normalized_alias": normalized}

    def start_voice_session(
        self, profile_id: str, conversation_session_id: str | None,
    ) -> dict[str, Any]:
        profile = self.profile(profile_id)
        if not profile:
            raise KeyError("profile not found")
        session_id, now = f"voice_{uuid.uuid4().hex[:16]}", utc_now()
        snapshot = bounded(profile)
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO aria_voice_sessions VALUES(?,?,?,?,?,?,NULL,NULL)",
                (
                    session_id, conversation_session_id, profile_id,
                    json.dumps(snapshot), "connecting", now,
                ),
            )
        return {"id": session_id, "conversation_session_id": conversation_session_id,
                "profile_snapshot": snapshot, "transport_state": "connecting",
                "started_at": now, "ended_at": None, "degraded_reason": None}

    def append_voice_turn(
        self, voice_session_id: str, role: str, content: str, metadata: dict[str, Any],
    ) -> None:
        with self.db.connect() as conn:
            voice = conn.execute(
                "SELECT conversation_session_id FROM aria_voice_sessions WHERE id=?",
                (voice_session_id,),
            ).fetchone()
        if not voice or not voice["conversation_session_id"]:
            raise KeyError("voice session has no conversation")
        now = utc_now()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO turns
                (id,session_id,role,content,evidence_json,created_at,modality,metadata_json)
                VALUES(?,?,?,?,?,?,?,?)""",
                (
                    f"turn_{uuid.uuid4().hex[:16]}", voice["conversation_session_id"],
                    role, content[:8_000], "[]", now, "voice",
                    json.dumps(bounded({
                        **metadata, "voice_session_id": voice_session_id,
                    })),
                ),
            )
            conn.execute(
                "UPDATE sessions SET updated_at=? WHERE id=?",
                (now, voice["conversation_session_id"]),
            )

    def record_execution(self, data: dict[str, Any]) -> dict[str, Any]:
        command_id = str(data["command_id"])
        if not any(item["id"] == command_id for item in COMMAND_MANIFEST):
            raise ValueError("unknown command")
        execution_id, now = f"exec_{uuid.uuid4().hex[:16]}", utc_now()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO aria_command_executions
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    execution_id, data.get("voice_session_id"), str(data["call_id"])[:160],
                    command_id, str(data.get("surface", "aria"))[:40],
                    json.dumps(bounded(data.get("arguments", {}))),
                    json.dumps(bounded(data.get("result", {}))),
                    json.dumps(list(data.get("evidence_ids", []))[:20]),
                    data.get("status", "succeeded"),
                    data.get("duration_ms"), str(data.get("error") or "")[:1_000] or None,
                    now,
                ),
            )
        return {"id": execution_id, **bounded(data), "created_at": now}

    def devhub(self, limit: int = 100) -> dict[str, Any]:
        with self.db.connect() as conn:
            sessions = conn.execute(
                "SELECT * FROM aria_voice_sessions ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
            executions = conn.execute(
                "SELECT * FROM aria_command_executions ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            transcripts: list[dict[str, Any]] = []
            for session in sessions:
                conversation_id = session["conversation_session_id"]
                if not conversation_id:
                    continue
                params: list[Any] = [conversation_id, session["started_at"]]
                end_clause = ""
                if session["ended_at"]:
                    end_clause = " AND created_at<=?"
                    params.append(session["ended_at"])
                turns = conn.execute(
                    """SELECT id,session_id,role,content,created_at,metadata_json
                    FROM turns WHERE session_id=? AND modality='voice'
                    AND created_at>=?""" + end_clause + " ORDER BY created_at",
                    tuple(params),
                ).fetchall()
                for turn in turns:
                    metadata = json.loads(turn["metadata_json"] or "{}")
                    correlated_session = metadata.get("voice_session_id")
                    if correlated_session and correlated_session != session["id"]:
                        continue
                    transcripts.append({
                        "id": turn["id"],
                        "voice_session_id": session["id"],
                        "conversation_session_id": turn["session_id"],
                        "role": turn["role"],
                        "content": turn["content"],
                        "metadata": metadata,
                        "created_at": turn["created_at"],
                    })
        return {
            "sessions": [{**dict(row), "profile_snapshot": json.loads(
                row["profile_snapshot_json"]
            )} for row in sessions],
            "executions": [{
                "id": row["id"], "voice_session_id": row["voice_session_id"],
                "call_id": row["call_id"], "command_id": row["command_id"],
                "surface": row["surface"], "arguments": json.loads(row["arguments_json"]),
                "result": json.loads(row["result_json"]),
                "evidence_ids": json.loads(row["evidence_ids_json"]),
                "status": row["status"], "duration_ms": row["duration_ms"],
                "error": row["error"], "created_at": row["created_at"],
            } for row in executions],
            "transcripts": transcripts,
            "coverage": {
                "definitions": len(COMMAND_MANIFEST),
                "voice_eligible": sum(item["eligible"] for item in COMMAND_MANIFEST),
                "protected": sum(item["confirmation_policy"] != "none"
                                 for item in COMMAND_MANIFEST),
                "missing_handlers": [],
                "scope": "registered_aria_actions",
                "gate": "registry_manifest_projection",
            },
        }
