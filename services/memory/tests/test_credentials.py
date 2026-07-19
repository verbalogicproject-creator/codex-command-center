from aria_memory.credentials import ProviderCredentialVault


def test_credential_envelope_is_encrypted_bound_and_expiring():
    vault = ProviderCredentialVault("test-secret-with-sufficient-entropy", 600)
    api_key = "test-user-owned-secret-value"
    token, issued = vault.seal("ws_first", api_key, now=1_000)

    assert api_key not in token
    assert issued.expires_at == "1970-01-01T00:26:40Z"
    opened = vault.open(token, "ws_first", now=1_500)
    assert opened is not None
    assert opened.api_key == api_key
    assert vault.open(token, "ws_second", now=1_500) is None
    assert vault.open(token, "ws_first", now=1_601) is None
    assert vault.open(token + "tampered", "ws_first", now=1_500) is None
    assert vault.open(token.rstrip("="), "ws_first", now=1_500) is None
    assert vault.open(token + "=", "ws_first", now=1_500) is None


def test_credential_cannot_be_opened_with_another_deployment_secret():
    first = ProviderCredentialVault("first-secret", 600)
    second = ProviderCredentialVault("second-secret", 600)
    token, _ = first.seal("ws_first", "test-user-owned-secret-value", now=1_000)

    assert second.open(token, "ws_first", now=1_100) is None


def test_provider_credential_endpoints_are_non_persistent(client, settings):
    api_key = "test-user-owned-secret-value"
    connected = client.post("/api/v1/provider-credentials/openai", json={
        "api_key": api_key,
    })

    assert connected.status_code == 200
    assert connected.json()["configured"] is True
    assert connected.json()["persistence"] == "encrypted_browser_session"
    assert api_key not in connected.text
    cookie = connected.headers["set-cookie"]
    assert api_key not in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/api/v1" in cookie
    assert "Max-Age" not in cookie

    status = client.get("/api/v1/provider-credentials/openai/status")
    assert status.status_code == 200
    assert status.json()["configured"] is True
    assert status.headers["cache-control"] == "no-store"

    for database in settings.data_dir.rglob("*.db"):
        assert api_key.encode() not in database.read_bytes()

    cleared = client.delete("/api/v1/provider-credentials/openai")
    assert cleared.status_code == 200
    assert cleared.json()["configured"] is False
    assert client.get(
        "/api/v1/provider-credentials/openai/status"
    ).json()["configured"] is False


def test_provider_credential_validation_never_echoes_key(client):
    invalid = "x" * 513
    response = client.post("/api/v1/provider-credentials/openai", json={
        "api_key": invalid,
    })

    assert response.status_code == 422
    assert invalid not in response.text


def test_byok_is_passed_only_to_request_scoped_screenshot_analysis(
    client, monkeypatch,
):
    captured = {}

    def fake_analyze(self, request, api_key=None):
        captured["api_key"] = api_key
        from aria_memory.models import ScreenshotAnalysis

        return ScreenshotAnalysis(
            image_hash="a" * 64,
            width=100,
            height=100,
            analyzed_width=100,
            analyzed_height=100,
            mime_type=request.mime_type,
            findings=["Inference: bounded test finding"],
            retained=False,
            model=self.deep_model,
            degraded=False,
        )

    monkeypatch.setattr(
        "aria_memory.toolbox.Toolbox.analyze_screenshot", fake_analyze,
    )
    api_key = "test-user-owned-secret-value"
    client.post("/api/v1/provider-credentials/openai", json={"api_key": api_key})
    response = client.post("/api/v1/screenshots/analyze", json={
        "repository": "Command Center",
        "user_request": "Review the interface.",
        "image_base64": "not-read-by-test-double",
        "mime_type": "image/png",
    })

    assert response.status_code == 200
    assert captured["api_key"] == api_key
    assert api_key not in response.text


def test_byok_is_passed_only_to_request_scoped_aria_chat(client, monkeypatch):
    captured = {}

    async def fake_run(self, request, api_key=None):
        captured["api_key"] = api_key
        return [{"type": "answer", "data": {"text": "Scoped", "degraded": False}}]

    monkeypatch.setattr("aria_memory.agent.Aria.run", fake_run)
    api_key = "test-user-owned-secret-value"
    client.post("/api/v1/provider-credentials/openai", json={"api_key": api_key})
    session = client.post("/api/v1/sessions", json={"title": "BYOK"}).json()
    response = client.post("/api/v1/chat/stream", json={
        "session_id": session["id"],
        "message": "Use the request-scoped model credential.",
    })

    assert response.status_code == 200
    assert "event: answer" in response.text
    assert captured["api_key"] == api_key
    assert api_key not in response.text
