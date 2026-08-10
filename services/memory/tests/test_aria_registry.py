import json
import re
from pathlib import Path

from aria_memory.aria_registry import AriaRegistry, COMMAND_MANIFEST
from aria_memory.db import APP_MIGRATION_VERSION, Database


ROOT = Path(__file__).resolve().parents[3]


def test_migration_8_and_manifest_reconcile_are_durable(tmp_path):
    path = tmp_path / "aria.db"
    db = Database(path)
    registry = AriaRegistry(db)
    with db.connect() as conn:
        versions = {row[0] for row in conn.execute(
            "SELECT version FROM app_migrations"
        ).fetchall()}
        default = conn.execute(
            "SELECT * FROM aria_profiles WHERE is_default=1"
        ).fetchone()
        conn.execute(
            "UPDATE aria_command_definitions SET safety_class='standard' "
            "WHERE id='approve_handoff'"
        )
        conn.commit()
    assert APP_MIGRATION_VERSION in versions
    assert default["id"] == "profile_default"
    assert db.count("aria_command_definitions") == len(COMMAND_MANIFEST)

    AriaRegistry(Database(path))
    with db.connect() as conn:
        protected = conn.execute(
            "SELECT safety_class,confirmation_policy FROM aria_command_definitions "
            "WHERE id='approve_handoff'"
        ).fetchone()
    assert tuple(protected) == ("protected", "exact_phrase")


def test_python_registry_matches_frontend_realtime_projection():
    source = (ROOT / "apps/web/lib/aria/commands.ts").read_text()
    projection = source.split(
        "export const ariaVoiceTools = [", 1
    )[1].split("] as const;", 1)[0]
    frontend = set(re.findall(r'\bname:\s*"([a-z_]+)"', projection))
    backend = {item["id"] for item in COMMAND_MANIFEST if item["eligible"]}
    assert frontend == backend


def test_scoped_catalog_profiles_aliases_and_reserved_phrase(client):
    aria = client.get("/api/v1/aria/commands?surface=aria").json()["items"]
    handoff = client.get("/api/v1/aria/commands?surface=handoff").json()["items"]
    assert "run_recall" not in {item["id"] for item in aria}
    assert "approve_handoff" in {item["id"] for item in handoff}
    assert "navigate_surface" in {item["id"] for item in aria}

    default = client.get("/api/v1/aria/profiles").json()["items"][0]
    created = client.post("/api/v1/aria/profiles", json={
        **default, "name": "Architecture focus", "preset": "architect",
    })
    assert created.status_code == 201
    profile = created.json()
    assert profile["is_default"] is False
    alias = client.post(f"/api/v1/aria/profiles/{profile['id']}/aliases", json={
        "command_id": "fit_graph", "alias": "  Frame   the GRAPH! ",
    })
    assert alias.status_code == 201
    assert alias.json()["normalized_alias"] == "frame the graph"
    collision = client.post(f"/api/v1/aria/profiles/{profile['id']}/aliases", json={
        "command_id": "navigate_surface", "alias": "frame-the-graph",
    })
    assert collision.status_code == 409
    reserved = client.post(f"/api/v1/aria/profiles/{profile['id']}/aliases", json={
        "command_id": "navigate_surface", "alias": "Approve this handoff.",
    })
    assert reserved.status_code == 409
    assert client.delete("/api/v1/aria/profiles/profile_default").status_code == 403


def test_voice_transcript_and_receipts_are_bounded_without_audio(client):
    conversation = client.post("/api/v1/sessions", json={"title": "Voice"}).json()
    voice = client.post("/api/v1/aria/voice-sessions", json={
        "profile_id": "profile_default",
        "conversation_session_id": conversation["id"],
    }).json()
    active = client.post(
        f"/api/v1/aria/voice-sessions/{voice['id']}/state",
        params={"state": "active"},
    )
    assert active.json()["transport_state"] == "active"
    stored = client.post(
        f"/api/v1/aria/voice-sessions/{voice['id']}/transcript",
        json={
            "role": "user", "content": "Open the graph.",
            "metadata": {"audio": "raw bytes", "dimensions": [10, 20]},
        },
    )
    assert stored.json() == {"stored": True, "raw_audio_stored": False}
    receipt = client.post("/api/v1/aria/executions", json={
        "voice_session_id": voice["id"],
        "call_id": "call_1",
        "command_id": "navigate_surface",
        "surface": "aria",
        "arguments": {"surface": "graph", "authorization": "Bearer secret"},
        "result": {"ok": True},
        "status": "succeeded",
        "duration_ms": 12,
    })
    assert receipt.status_code == 201
    turns = client.get(
        f"/api/v1/sessions/{conversation['id']}/turns"
    ).json()["items"]
    assert turns[0]["modality"] == "voice"
    assert "audio" not in turns[0]["metadata"]
    devhub = client.get("/api/v1/aria/devhub").json()
    encoded = json.dumps(devhub)
    assert "Bearer secret" not in encoded
    assert "authorization" not in devhub["executions"][0]["arguments"]
    assert devhub["coverage"]["scope"] == "registered_aria_actions"
    assert devhub["transcripts"][0]["content"] == "Open the graph."
    assert devhub["transcripts"][0]["voice_session_id"] == voice["id"]
    assert devhub["transcripts"][0]["metadata"]["voice_session_id"] == voice["id"]

    refused = client.delete(
        "/api/v1/aria/voice-sessions?confirmation=delete"
    )
    assert refused.status_code == 409
    deleted = client.delete(
        "/api/v1/aria/voice-sessions",
        params={"confirmation": "Delete Aria voice history."},
    )
    assert deleted.json()["deleted_sessions"] == 1
