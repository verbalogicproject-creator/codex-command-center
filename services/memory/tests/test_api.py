import json

from fastapi.testclient import TestClient

from aria_memory.app import create_app


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
    assert body["embeddings"]["coverage"] == 1
    assert body["degraded"] is True  # no live OpenAI key


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
