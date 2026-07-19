from __future__ import annotations

from fastapi.testclient import TestClient

from aria_memory.app import create_app
from aria_memory.mcp_app import MCP_PROTOCOL_VERSION, create_mcp_app


def paired_token(settings) -> str:
    api = TestClient(create_app(settings))
    assert api.post(
        "/api/v1/auth/demo",
        json={"code": settings.demo_access_code},
    ).status_code == 200
    code = api.post("/api/v1/auth/pair/start").json()["code"]
    response = api.post("/api/v1/auth/pair", json={"code": code})
    assert response.status_code == 200
    return response.json()["workspace_token"]


def test_mcp_only_app_authentication_scope_and_protocol(settings):
    token = paired_token(settings)
    client = TestClient(create_mcp_app(settings))

    assert client.get("/healthz").json() == {
        "status": "ok",
        "service": "codex-command-center-mcp",
    }
    unauthorized = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {},
    })
    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "unauthorized"

    initialized = client.post(
        "/mcp",
        headers={"X-Command-Center-Token": token},
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {},
        },
    )
    assert initialized.status_code == 200
    assert initialized.headers["MCP-Protocol-Version"] == MCP_PROTOCOL_VERSION
    assert initialized.json()["result"]["serverInfo"]["name"] == (
        "codex-command-center"
    )

    tools = client.post(
        "/mcp",
        headers={"X-Command-Center-Token": token},
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/list",
            "params": {},
        },
    ).json()["result"]["tools"]
    assert len(tools) == 10
    assert {tool["name"] for tool in tools} >= {
        "load_handoff",
        "build_task_pack",
        "get_capability",
    }

    assert client.get("/api/v1/status").status_code == 404
    assert client.get("/docs").status_code == 404
    well_known = client.get("/.well-known/oauth-protected-resource")
    assert well_known.status_code == 404
    assert well_known.json()["error"]["code"] == "oauth_metadata_unavailable"


def test_mcp_only_app_notifications_and_batches(settings):
    token = paired_token(settings)
    client = TestClient(create_mcp_app(settings))
    headers = {"X-Command-Center-Token": token}

    notification = client.post("/mcp", headers=headers, json={
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    })
    assert notification.status_code == 202

    batch = client.post("/mcp", headers=headers, json=[
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "initialize",
            "params": {},
        },
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/list",
            "params": {},
        },
    ])
    assert batch.status_code == 200
    assert [item["id"] for item in batch.json()] == [4, 5]


def test_mcp_cloud_surface_does_not_require_browser_byok_secret(settings):
    cloud = settings.__class__(**{
        **settings.__dict__,
        "app_env": "cloud",
        "database_url": "postgresql://unused-until-authenticated",
        "provider_credential_secret": None,
    })

    client = TestClient(create_mcp_app(cloud))
    assert client.get("/healthz").status_code == 200
