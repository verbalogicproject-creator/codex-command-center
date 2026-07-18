from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

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
