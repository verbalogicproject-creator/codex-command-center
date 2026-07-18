import json

from fastapi.testclient import TestClient

from aria_memory.app import create_app
from aria_memory.context import estimate_tokens


def test_auth_rejects_bad_code(settings):
    client = TestClient(create_app(settings))
    response = client.post("/api/v1/auth/demo", json={"code": "wrong"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_code"


def test_status_reports_seed_and_embeddings(client):
    result = client.get("/api/v1/status")
    assert result.status_code == 200
    body = result.json()
    assert 40 <= body["memories"] <= 60
    assert body["documents"] == 5
    assert body["embeddings"]["coverage"] == 1
    assert body["degraded"] is True  # no live OpenAI key


def test_voice_token_requires_server_key(client):
    result = client.post("/api/v1/realtime/token")
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "voice_unavailable"


def test_voice_token_uses_short_lived_server_minted_secret(settings, monkeypatch):
    configured = settings.__class__(**{**settings.__dict__, "openai_api_key": "server-secret"})
    captured = {}

    class Upstream:
        status_code = 200

        @staticmethod
        def json():
            return {"value": "ek_test", "expires_at": 123}

    class FakeAsyncClient:
        def __init__(self, **_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, url, **kwargs):
            captured.update(url=url, **kwargs)
            return Upstream()

    monkeypatch.setattr("aria_memory.app.httpx.AsyncClient", FakeAsyncClient)
    client = TestClient(create_app(configured))
    client.post("/api/v1/auth/demo", json={"code": "test-code"})
    result = client.post("/api/v1/realtime/token")
    assert result.status_code == 200
    assert result.json()["value"] == "ek_test"
    assert captured["url"].endswith("/realtime/client_secrets")
    assert captured["headers"]["Authorization"] == "Bearer server-secret"
    assert captured["json"]["expires_after"]["seconds"] == 600
    assert "confirm" not in captured["json"]["session"].get("tools", [])


def test_recall_contract_and_hero_evidence(client):
    result = client.post("/api/v1/recall", json={
        "query": "fast private mobile assistant", "limit": 12,
    })
    assert result.status_code == 200
    body = result.json()
    projects = {hit["memory"]["project"] for hit in body["hits"]}
    assert {"Hexagon", "Command Center", "Project Memory"} <= projects
    assert body["trace"]["query_embedding_calls"] == 1
    assert all("provenance" in hit for hit in body["hits"])


def test_session_and_fallback_sse_proposal(client):
    session = client.post("/api/v1/sessions", json={"title": "Hero"}).json()
    result = client.post("/api/v1/chat/stream", json={
        "session_id": session["id"],
        "message": "Which projects power a private mobile assistant? Propose a decision.",
        "deep_synthesis": True,
    })
    assert result.status_code == 200
    assert "event: evidence" in result.text
    assert "event: render" in result.text
    assert "event: proposal" in result.text
    assert "event: answer" in result.text
    turns = client.get(f"/api/v1/sessions/{session['id']}/turns").json()["items"]
    assert [turn["role"] for turn in turns] == ["user", "assistant"]
    assert turns[1]["evidence_ids"]


def test_workspace_isolation(settings):
    app = create_app(settings)
    first, second = TestClient(app), TestClient(app)
    first.post("/api/v1/auth/demo", json={"code": "test-code"})
    second.post("/api/v1/auth/demo", json={"code": "test-code"})
    first.post("/api/v1/sessions", json={"title": "Only first"})
    assert len(first.get("/api/v1/sessions").json()["items"]) == 1
    assert second.get("/api/v1/sessions").json()["items"] == []


def test_one_time_pairing_joins_browser_workspace(settings):
    app = create_app(settings)
    browser, plugin = TestClient(app), TestClient(app)
    browser.post("/api/v1/auth/demo", json={"code": "test-code"})
    code = browser.post("/api/v1/auth/pair/start").json()["code"]
    paired = plugin.post("/api/v1/auth/pair", json={"code": code})
    assert paired.status_code == 200

    proposal = plugin.post("/api/v1/proposals", json={
        "operation": "record_fact",
        "payload": {"project": "Command Center", "title": "Paired", "content": "Pending"},
        "rationale": "Pairing test",
    }).json()
    pending = browser.get("/api/v1/proposals?status=pending").json()["items"]
    assert pending[0]["id"] == proposal["id"]
    assert plugin.post("/api/v1/auth/pair", json={"code": code}).status_code == 401


def test_memory_type_path_is_enforced(client):
    assert client.get("/api/v1/memories/facts/fact_pm_01").status_code == 200
    assert client.get("/api/v1/memories/episodes/fact_pm_01").status_code == 404


def test_recall_quota(settings):
    limited = settings.__class__(**{**settings.__dict__, "max_direct_recalls": 1})
    client = TestClient(create_app(limited))
    client.post("/api/v1/auth/demo", json={"code": "test-code"})
    assert client.post("/api/v1/recall", json={"query": "memory"}).status_code == 200
    result = client.post("/api/v1/recall", json={"query": "memory"})
    assert result.status_code == 429
    assert result.json()["error"]["code"] == "quota_exceeded"


def test_declared_document_recall_is_explainable(client):
    result = client.post("/api/v1/documents/recall", json={
        "query": "private mobile inference risk", "limit": 5, "mode": "hybrid",
    })
    assert result.status_code == 200
    body = result.json()
    assert any(hit["document"]["id"] == "doc_hexagon" for hit in body["hits"])
    assert all(hit["dimension_contributions"] for hit in body["hits"])
    assert "declared-dimensions" in body["trace"]["signals"]
    assert all(not hit["document"]["source_uri"].startswith("/") for hit in body["hits"])


def test_context_pack_is_bounded_and_keeps_entity_classes_distinct(client):
    result = client.post("/api/v1/context/pack", json={
        "prompt": "human gated memory writes and safe edit points",
        "repository": "Command Center",
        "token_budget": 1600,
    })
    assert result.status_code == 200
    body = result.json()
    assert body["token_estimate"] <= body["token_budget"] == 1600
    assert estimate_tokens(result.text) == body["token_estimate"]
    assert body["repository_identity"]["repository"] == "Command Center"
    assert body["documents"]
    assert body["facts"]
    assert all(item["entity_type"] == "fact" for item in body["facts"])
    assert all("source_uri" in item for item in body["documents"])
    assert body["safe_edit_points"]
    assert body["risk_areas"]
    assert body["routing"]["prompt_in_url"] is False
    assert body["omitted_candidate_count"] > 0


def test_proposals_restore_and_unknown_hook_event_is_rejected(client):
    session = client.post("/api/v1/sessions", json={"title": "Restore"}).json()
    proposal = client.post("/api/v1/proposals", json={
        "session_id": session["id"],
        "operation": "record_fact",
        "payload": {"project": "Command Center", "title": "Pending", "content": "Review me"},
        "rationale": "Browser review",
        "evidence_ids": ["fact_cc_07"],
    })
    assert proposal.status_code == 201
    restored = client.get(f"/api/v1/sessions/{session['id']}/proposals").json()["items"]
    assert restored[0]["id"] == proposal.json()["id"]
    assert restored[0]["status"] == "pending"

    unknown = client.post("/api/v1/hooks/events", json={
        "kind": "random_noise", "repository": "Command Center",
    })
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "validation_error"


def test_stop_hook_drafts_pending_memory_without_durable_mutation(client):
    before = client.get("/api/v1/status").json()
    result = client.post("/api/v1/hooks/events", json={
        "kind": "stop", "repository": "Command Center",
        "detail": {
            "summary": "Added context packet tests.",
            "draft_proposal": True,
            "raw_prompt": "must be dropped",
        },
        "source_ids": ["doc_command_center"],
    })
    assert result.status_code == 202
    body = result.json()
    assert body["proposal"]["status"] == "pending"
    after = client.get("/api/v1/status").json()
    assert after["memories"] == before["memories"]
    assert after["proposals_pending"] == before["proposals_pending"] + 1


def test_stop_hook_telemetry_does_not_create_proposal_by_default(client):
    before = client.get("/api/v1/status").json()
    result = client.post("/api/v1/hooks/events", json={
        "kind": "stop", "repository": "Command Center",
        "detail": {"summary": "Routine turn completed."},
    })
    assert result.status_code == 202
    assert result.json()["proposal"] is None
    after = client.get("/api/v1/status").json()
    assert after["proposals_pending"] == before["proposals_pending"]


def test_mud_refusal_is_visible_in_chat_and_creates_no_proposal(client):
    session = client.post("/api/v1/sessions", json={"title": "MUD"}).json()
    before = client.get("/api/v1/status").json()
    result = client.post("/api/v1/chat/stream", json={
        "session_id": session["id"],
        "message": "Merge LifeOS and Hexagon into Command Center. Propose a decision.",
        "deep_synthesis": False,
    })
    assert result.status_code == 200
    assert "event: answer" in result.text
    assert "**Refusal:**" in result.text
    assert "MUD" not in result.text  # refusal is phrased for a non-technical user
    after = client.get("/api/v1/status").json()
    assert after["memories"] == before["memories"]
    assert after["proposals_pending"] == before["proposals_pending"]
