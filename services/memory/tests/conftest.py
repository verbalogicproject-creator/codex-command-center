from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aria_memory.app import create_app
from aria_memory.config import ROOT, Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        seed_path=ROOT / "fixtures" / "demo" / "memories.json",
        demo_access_code="test-code",
        cookie_secret="test-secret-with-sufficient-entropy",
        embedding_api_key=None,
        embedding_provider="hash",
        max_aria_turns=20,
        max_direct_recalls=100,
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    result = TestClient(create_app(settings))
    response = result.post("/api/v1/auth/demo", json={"code": "test-code"})
    assert response.status_code == 200
    return result
