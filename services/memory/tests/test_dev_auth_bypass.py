from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aria_memory.app import COOKIE_NAME, create_app, sign
from aria_memory.config import Settings
from aria_memory.mcp_app import create_mcp_app


def with_bypass(settings: Settings, **overrides) -> Settings:
    return settings.__class__(**{
        **settings.__dict__,
        "dev_auth_bypass": True,
        "dev_bind_host": "127.0.0.1",
        **overrides,
    })


def test_auth_is_required_by_default(settings):
    client = TestClient(create_app(settings))
    assert client.get("/api/v1/status").status_code == 401


def test_dev_bypass_reuses_one_workspace_across_api_and_mcp_restarts(settings):
    configured = with_bypass(
        settings, dev_workspace_id="ws_0123456789abcdef",
    )
    first = TestClient(create_app(configured), base_url="http://localhost")
    created = first.post("/api/v1/sessions", json={"title": "Persistent local"})
    assert created.status_code == 201

    restarted = TestClient(create_app(configured), base_url="http://127.0.0.1")
    sessions = restarted.get("/api/v1/sessions")
    assert sessions.status_code == 200
    assert [item["id"] for item in sessions.json()["items"]] == [created.json()["id"]]

    mcp = TestClient(create_mcp_app(configured), base_url="http://localhost")
    initialized = mcp.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {},
    })
    assert initialized.status_code == 200
    assert (settings.data_dir / "dev-workspace-id").read_text().strip() == (
        "ws_0123456789abcdef"
    )


def test_dev_bypass_can_adopt_authenticated_workspace_without_guessing(settings):
    normal = TestClient(create_app(settings), base_url="http://localhost")
    authenticated = normal.post(
        "/api/v1/auth/demo", json={"code": settings.demo_access_code},
    ).json()
    workspace_id = authenticated["workspace_id"]

    bypass = TestClient(create_app(with_bypass(settings)), base_url="http://localhost")
    bypass.cookies.set(COOKIE_NAME, sign(workspace_id, settings.cookie_secret))
    assert bypass.get("/api/v1/status").status_code == 200
    assert (settings.data_dir / "dev-workspace-id").read_text().strip() == workspace_id


def test_dev_bypass_fails_closed_when_existing_workspaces_are_ambiguous(settings):
    for workspace_id in ("ws_1111111111111111", "ws_2222222222222222"):
        client = TestClient(create_app(settings), base_url="http://localhost")
        client.cookies.set(COOKIE_NAME, sign(workspace_id, settings.cookie_secret))
        assert client.get("/api/v1/status").status_code == 200

    bypass = TestClient(create_app(with_bypass(settings)), base_url="http://localhost")
    response = bypass.get("/api/v1/status")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "dev_workspace_unresolved"


@pytest.mark.parametrize("bind_host", ["0.0.0.0", "192.168.1.10", "command.example"])
def test_dev_bypass_rejects_non_loopback_bind_configuration(settings, bind_host):
    with pytest.raises(RuntimeError, match="loopback"):
        create_app(with_bypass(settings, dev_bind_host=bind_host))
    with pytest.raises(RuntimeError, match="loopback"):
        create_mcp_app(with_bypass(settings, dev_bind_host=bind_host))


def test_dev_bypass_requires_explicit_bind_and_local_app_environment(settings):
    with pytest.raises(RuntimeError, match="explicit loopback"):
        create_app(with_bypass(settings, dev_bind_host=None))
    with pytest.raises(RuntimeError, match="APP_ENV=local"):
        create_app(with_bypass(settings, app_env="cloud"))


def test_dev_bypass_rejects_non_loopback_request_host_and_origin(settings):
    configured = with_bypass(settings, dev_workspace_id="ws_0123456789abcdef")
    external = TestClient(create_app(configured), base_url="http://192.168.1.20")
    assert external.get("/api/v1/status").status_code == 403

    local = TestClient(create_app(configured), base_url="http://localhost")
    assert local.get(
        "/api/v1/status", headers={"Origin": "https://command.example"},
    ).status_code == 403


def test_dev_bypass_keeps_durable_confirmation_browser_only(settings):
    configured = with_bypass(settings, dev_workspace_id="ws_0123456789abcdef")
    client = TestClient(create_app(configured), base_url="http://localhost")
    before = client.get("/api/v1/status").json()["memories"]
    proposal = client.post("/api/v1/proposals", json={
        "operation": "record_fact",
        "payload": {"project": "Command Center", "title": "Pending", "content": "Review"},
        "rationale": "Boundary test",
    })
    assert proposal.status_code == 201
    assert proposal.json()["status"] == "pending"
    assert client.get("/api/v1/status").json()["memories"] == before

    client.cookies.set(
        COOKIE_NAME,
        sign("ws_0123456789abcdef", settings.cookie_secret),
    )
    originless = client.post(f"/api/v1/proposals/{proposal.json()['id']}/confirm")
    assert originless.status_code == 403
    confirmed = client.post(
        f"/api/v1/proposals/{proposal.json()['id']}/confirm",
        headers={"Origin": "http://localhost:3000"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
