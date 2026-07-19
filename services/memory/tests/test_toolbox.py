from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from aria_memory.db import Database
from aria_memory.toolbox import Toolbox

ROOT = Path(__file__).resolve().parents[3]
ARCHITECTURE_FIXTURE = (
    ROOT / "fixtures" / "demo" / "architecture" / "frontmatter-component.md"
)


def _png() -> str:
    output = io.BytesIO()
    Image.new("RGB", (320, 180), "#17334a").save(output, "PNG")
    return base64.b64encode(output.getvalue()).decode()


def test_capabilities_are_seeded_versioned_and_trust_filtered(client):
    seeded = client.get("/api/v1/capabilities").json()["items"]
    assert {item["stable_id"] for item in seeded} >= {
        "taste-frontend-redesign-interview",
        "frontend-redesign-interview",
        "mobile-accessibility-review",
        "graph-canvas-integration",
        "evidence-bound-coding-plan",
        "safe-deployment-preparation",
    }
    body = {
        "stable_id": "workspace-review",
        "name": "Workspace review",
        "kind": "workflow",
        "description": "A workspace-specific review.",
        "triggers": ["review"],
        "instructions": "Inspect evidence, then interview the user.",
        "repositories": ["Command Center"],
        "required_tools": ["get_evidence"],
        "trust_status": "workspace",
        "provenance": "Created in this test workspace.",
    }
    first = client.post("/api/v1/capabilities", json=body).json()
    second = client.post("/api/v1/capabilities", json={
        **body, "instructions": "Inspect receipts, then interview the user.",
    }).json()
    assert (first["version"], second["version"]) == (1, 2)
    assert first["content_hash"] != second["content_hash"]
    latest = client.get("/api/v1/capabilities/workspace-review").json()
    assert latest["version"] == 2

    client.post("/api/v1/capabilities", json={
        **body, "stable_id": "unsafe-review", "trust_status": "untrusted",
    })
    trusted = client.get("/api/v1/capabilities").json()["items"]
    assert "unsafe-review" not in {item["stable_id"] for item in trusted}


def test_taste_capability_is_verified_recommended_and_injected(client):
    capability = client.get(
        "/api/v1/capabilities/taste-frontend-redesign-interview"
    ).json()
    assert capability["trust_status"] == "verified"
    assert capability["kind"] == "workflow"
    assert "Leonxlnx" in capability["provenance"]
    assert "aa194351b246" in capability["provenance"]
    assert "DESIGN_VARIANCE" in capability["instructions"]
    assert "one focused question at a time" in capability["instructions"]

    recommended = client.post("/api/v1/capabilities/recommend", json={
        "request": (
            "Use Taste and a screenshot to interview me about a frontend "
            "redesign, design dials, typography, motion, and visual hierarchy."
        ),
        "repository": "Command Center",
        "screenshot_findings": [
            "The current interface may have weak visual hierarchy.",
        ],
    }).json()["items"]
    assert recommended[0]["capability"]["stable_id"] == (
        "taste-frontend-redesign-interview"
    )

    handoff = client.post("/api/v1/handoffs", json={
        "repository": "Command Center",
        "original_request": "Redesign the Command Center from this screenshot.",
        "capability_refs": [
            f"taste-frontend-redesign-interview@{capability['version']}",
        ],
        "open_plan": [
            "Load the pinned architecture and screenshot inferences.",
            "Interview before editing.",
        ],
        "token_budget": 3_000,
    }).json()
    assert client.post(
        f"/api/v1/handoffs/{handoff['id']}/publish"
    ).status_code == 200
    loaded = client.post("/api/v1/handoffs/load", json={
        "handoff_id": handoff["id"],
        "repository": "Command Center",
        "client_name": "Codex",
        "session_id": "taste-redesign-session",
    }).json()
    workflow = loaded["workflow_instructions"][0]
    assert workflow["capability_id"] == "taste-frontend-redesign-interview"
    assert workflow["version"] == capability["version"]
    assert workflow["content_hash"] == capability["content_hash"]
    assert "Do not edit code merely because this workflow was loaded" in (
        workflow["instructions"]
    )

    through_mcp = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 19,
        "method": "tools/call",
        "params": {
            "name": "get_capability",
            "arguments": {
                "capability_id": "taste-frontend-redesign-interview",
                "version": capability["version"],
            },
        },
    }).json()["result"]["structuredContent"]
    assert through_mcp["content_hash"] == capability["content_hash"]


def test_new_verified_builtins_seed_existing_workspaces_idempotently(tmp_path):
    database = Database(tmp_path / "capability-upgrade.db")
    first = Toolbox(database, None, "offline")  # type: ignore[arg-type]
    assert first.get_capability("frontend-redesign-interview") is not None
    with database.transaction() as connection:
        connection.execute(
            "DELETE FROM capabilities WHERE stable_id=?",
            ("taste-frontend-redesign-interview",),
        )
    assert first.get_capability("taste-frontend-redesign-interview") is None

    second = Toolbox(database, None, "offline")  # type: ignore[arg-type]
    seeded = second.get_capability("taste-frontend-redesign-interview")
    assert seeded is not None
    assert seeded.version == 1
    Toolbox(database, None, "offline")  # type: ignore[arg-type]
    with database.connect() as connection:
        versions = connection.execute(
            "SELECT COUNT(*) FROM capabilities WHERE stable_id=?",
            ("taste-frontend-redesign-interview",),
        ).fetchone()[0]
    assert versions == 1


def test_screenshot_is_validated_resized_and_not_retained(client):
    result = client.post("/api/v1/screenshots/analyze", json={
        "repository": "Command Center",
        "user_request": "Improve the hierarchy for mobile.",
        "image_base64": _png(),
        "mime_type": "image/png",
        "retain": True,
    })
    assert result.status_code == 200
    body = result.json()
    assert (body["width"], body["height"]) == (320, 180)
    assert body["retained"] is False
    assert body["findings_are_inferences"] is True
    assert len(body["image_hash"]) == 64

    mismatch = client.post("/api/v1/screenshots/analyze", json={
        "repository": "Command Center", "user_request": "Review",
        "image_base64": _png(), "mime_type": "image/jpeg",
    })
    assert mismatch.status_code == 422


def test_redesign_handoff_has_deterministic_planning_receipt_and_tour(client):
    created = client.post("/api/v1/handoffs", json={
        "repository": "Command Center",
        "original_request": "Redesign the Handoff Builder and Guided Tour.",
    })
    assert created.status_code == 201
    handoff = created.json()
    assert handoff["capability_refs"][0].startswith(
        "taste-frontend-redesign-interview@"
    )
    assert 1 <= len(handoff["open_plan"]) <= 12
    receipt = handoff["planning_receipt"]
    assert receipt["schema_version"] == "command-center-planning-receipt-v1"
    assert receipt["model"] == "deterministic-taste-plan-v1"
    assert receipt["capability_reference"]["content_hash"]
    assert receipt["degraded"] is True
    assert "sol_planning_requires_byok" in receipt["degraded_reasons"]

    restored = client.get(f"/api/v1/handoffs/{handoff['id']}").json()
    assert restored["planning_receipt"] == receipt
    tour = client.post("/api/v1/tours/script", json={
        "mode": "redesign",
        "repository": "Command Center",
        "handoff_id": handoff["id"],
    })
    assert tour.status_code == 200
    script = tour.json()
    assert script["schema_version"] == "command-center-tour-script-v1"
    assert script["model"] == "deterministic-evidence-tour-v1"
    assert [step["id"] for step in script["steps"]] == [
        "redesign-problem",
        "redesign-screenshot-boundary",
        "redesign-taste",
        "redesign-receipts",
        "redesign-open-plan",
        "redesign-publication",
        "redesign-activation",
    ]
    assert script["steps"][1]["pause_reason"]
    assert script["steps"][-1]["pause_reason"]


def test_sol_and_luna_use_bounded_post_analysis_receipts(client, monkeypatch):
    calls: list[dict] = []

    class FakeResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            if kwargs["model"] == "gpt-5.6-luna":
                return SimpleNamespace(output_text=json.dumps([{
                    "id": "redesign-problem",
                    "surface": "handoff",
                    "target": "heading",
                    "evidence_ids": [],
                    "narration": "Review the bounded redesign intent.",
                    "action": "Review the problem.",
                    "pause_reason": None,
                }]))
            if isinstance(kwargs.get("input"), list):
                return SimpleNamespace(output_text=(
                    "The hierarchy may need a clearer primary action.\n"
                    "The layout may need narrow-screen verification."
                ))
            return SimpleNamespace(output_text=(
                "Report all pinned receipts before planning.\n"
                "Ask one focused design question before edits.\n"
                "Present a bounded responsive plan for approval."
            ))

    class FakeOpenAI:
        def __init__(self, **_kwargs):
            self.responses = FakeResponses()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    connected = client.post("/api/v1/provider-credentials/openai", json={
        "api_key": "sk-test-" + "x" * 32,
    })
    assert connected.status_code == 200
    analysis = client.post("/api/v1/screenshots/analyze", json={
        "repository": "Command Center",
        "user_request": "Redesign the Handoff Builder.",
        "image_base64": _png(),
        "mime_type": "image/png",
    }).json()
    assert analysis["degraded"] is False

    handoff = client.post("/api/v1/handoffs", json={
        "repository": "Command Center",
        "original_request": "Redesign the Handoff Builder.",
        "screenshot": analysis,
    }).json()
    assert handoff["planning_receipt"]["model"] == "gpt-5.6-sol"
    planning_call = next(
        call for call in calls
        if call["model"] == "gpt-5.6-sol"
        and isinstance(call.get("input"), str)
    )
    assert "data:image" not in planning_call["input"]
    assert analysis["image_hash"] in planning_call["input"]
    assert all(len(step) <= 500 for step in handoff["open_plan"])

    tour = client.post("/api/v1/tours/script", json={
        "mode": "redesign",
        "handoff_id": handoff["id"],
    }).json()
    assert tour["model"] == "gpt-5.6-luna"
    assert tour["degraded"] is False
    luna_call = next(call for call in calls if call["model"] == "gpt-5.6-luna")
    assert "data:image" not in luna_call["input"]


def test_handoff_publication_immutability_repository_guard_and_activation(client):
    analysis = client.post("/api/v1/screenshots/analyze", json={
        "repository": "Command Center", "user_request": "Redesign the graph panel.",
        "image_base64": _png(), "mime_type": "image/png",
    }).json()
    created = client.post("/api/v1/handoffs", json={
        "repository": "Command Center",
        "original_request": "Redesign the graph panel.",
        "screenshot": analysis,
        "capability_refs": ["frontend-redesign-interview@1"],
        "open_plan": ["Interview before editing.", "Verify the graph on mobile."],
    })
    assert created.status_code == 201
    handoff = created.json()
    assert handoff["status"] == "draft"
    assert handoff["codex_command"].startswith("/plan Load Command Center handoff")

    published = client.post(f"/api/v1/handoffs/{handoff['id']}/publish")
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert client.patch(f"/api/v1/handoffs/{handoff['id']}", json={
        "open_plan": ["Mutate published"],
    }).status_code == 409

    mismatch = client.post("/api/v1/handoffs/load", json={
        "handoff_id": handoff["id"], "repository": "Another Repository",
    })
    assert mismatch.status_code == 403
    loaded = client.post("/api/v1/handoffs/load", json={
        "handoff_id": handoff["id"], "repository": "Command Center",
        "client_name": "Codex", "session_id": "session-1",
    })
    assert loaded.status_code == 200
    packet = loaded.json()
    assert packet["interview_required"] is True
    assert packet["planning_receipt"]["schema_version"] == (
        "command-center-planning-receipt-v1"
    )
    assert packet["workflow_instructions"][0]["version"] == 1
    assert all(item["classification"] == "inference"
               for item in packet["screenshot_observations"])
    assert packet["activation_id"].startswith("activate_")

    next_version = client.post(f"/api/v1/handoffs/{handoff['id']}/versions", json={
        "open_plan": ["A new immutable version."],
    })
    assert next_version.status_code == 200
    assert next_version.json()["version"] == 2
    assert next_version.json()["status"] == "draft"


def test_published_handoff_keeps_pinned_architecture_and_accepts_registered_alias(client):
    content = ARCHITECTURE_FIXTURE.read_text(encoding="utf-8")

    def sync(revision: str, document_content: str) -> dict:
        response = client.post("/api/v1/architecture/sync", json={
            "repository": {
                "id": "synthetic-architecture",
                "name": "Synthetic Architecture",
                "aliases": ["synthetic-checkout"],
            },
            "source_revision": revision,
            "manifest_hash": "a" * 64,
            "documents": [{
                "source_uri": "docs/architecture.md",
                "content": document_content,
            }],
        })
        assert response.status_code == 200
        return response.json()

    first = sync("revision-one", content)
    created = client.post("/api/v1/handoffs", json={
        "repository": "Synthetic Architecture",
        "original_request": "Change the frontmatter component contract safely.",
        "capability_refs": ["evidence-bound-coding-plan@1"],
        "open_plan": ["Inspect the pinned evidence.", "Interview before editing."],
    })
    assert created.status_code == 201
    handoff = created.json()
    pinned = handoff["architecture"]["snapshot_receipt"]
    assert pinned["snapshot_id"] == first["snapshot"]["id"]
    pinned_source = next(
        item["id"] for item in handoff["evidence_sources"]
        if item["entity_type"] == "architecture_document"
    )
    assert client.post(f"/api/v1/handoffs/{handoff['id']}/publish").status_code == 200

    second = sync(
        "revision-two",
        content.replace(
            "The fixture is synthetic",
            "The revised fixture is synthetic",
        ),
    )
    assert second["snapshot"]["id"] != first["snapshot"]["id"]

    loaded = client.post("/api/v1/handoffs/load", json={
        "handoff_id": handoff["id"],
        "repository": "synthetic-checkout",
        "client_name": "Codex",
        "session_id": "pinned-session",
    })
    assert loaded.status_code == 200
    packet = loaded.json()
    assert (
        packet["declared_architecture"]["snapshot_receipt"]["snapshot_id"]
        == first["snapshot"]["id"]
    )
    assert pinned_source in {
        receipt["evidence_id"] for receipt in packet["evidence_receipts"]
    }

    evidence = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": "get_evidence",
            "arguments": {"source_id": pinned_source},
        },
    }).json()["result"]["structuredContent"]
    assert evidence["entity_type"] == "architecture_document"
    assert evidence["evidence"]["snapshot_id"] == first["snapshot"]["id"]

    task_pack = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {
            "name": "build_task_pack",
            "arguments": {
                "prompt": "frontmatter contract",
                "repository": "synthetic-checkout",
            },
        },
    }).json()["result"]["structuredContent"]
    assert task_pack["packet_schema"] == "command-center-task-pack-v2"
    assert (
        task_pack["architecture_brief"]["snapshot_receipt"]["snapshot_id"]
        == second["snapshot"]["id"]
    )
    graph = client.get("/api/v1/graph").json()
    node_ids = {node["id"] for node in graph["nodes"]}
    assert pinned_source in node_ids
    assert "client:codex" in node_ids
    assert any(
        edge["source"] == pinned_source
        and edge["target"] == f"handoff:{handoff['id']}"
        and edge["type"] == "selected_for_handoff"
        for edge in graph["edges"]
    )
    assert any(
        edge["source"] == f"handoff:{handoff['id']}"
        and edge["target"] == "client:codex"
        and edge["type"] == "activated_in_codex"
        for edge in graph["edges"]
    )


def test_pairing_token_auth_mcp_and_revocation(settings):
    from fastapi.testclient import TestClient
    from aria_memory.app import create_app

    app = create_app(settings)
    browser, client = TestClient(app), TestClient(app)
    browser.post("/api/v1/auth/demo", json={"code": "test-code"})
    code = browser.post("/api/v1/auth/pair/start").json()["code"]
    token = client.post("/api/v1/auth/pair", json={"code": code}).json()["workspace_token"]
    client.cookies.clear()
    headers = {"X-Command-Center-Token": token}
    initialized = client.post("/mcp", headers=headers, json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {},
    })
    assert initialized.status_code == 200
    assert initialized.json()["result"]["serverInfo"]["name"] == "codex-command-center"
    assert initialized.json()["result"]["serverInfo"]["version"] == "0.5.0"
    tools = client.post("/mcp", headers=headers, json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
    }).json()["result"]["tools"]
    assert {item["name"] for item in tools} >= {
        "search_capabilities", "load_handoff", "build_task_pack",
        "propose_memory_write",
    }
    assert client.post("/api/v1/auth/token/revoke", headers=headers).json()["revoked"] is True
    assert client.post("/mcp", headers=headers, json={
        "jsonrpc": "2.0", "id": 3, "method": "initialize", "params": {},
    }).status_code == 401


def test_pairing_code_survives_service_restart(settings):
    from fastapi.testclient import TestClient
    from aria_memory.app import create_app

    browser = TestClient(create_app(settings))
    browser.post("/api/v1/auth/demo", json={"code": "test-code"})
    code = browser.post("/api/v1/auth/pair/start").json()["code"]

    restarted = TestClient(create_app(settings))
    paired = restarted.post("/api/v1/auth/pair", json={"code": code})
    assert paired.status_code == 200
    assert paired.json()["workspace_token"].startswith("ccw_")
    assert restarted.post("/api/v1/auth/pair", json={"code": code}).status_code == 401
