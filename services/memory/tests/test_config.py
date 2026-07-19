import pytest

from aria_memory.app import create_app
from aria_memory.config import ROOT, Settings


def test_relative_env_paths_resolve_from_repository_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATA_DIR", "./data")
    monkeypatch.setenv("DEMO_SEED", "./fixtures/demo/memories.json")

    settings = Settings()

    assert settings.data_dir == (ROOT / "data").resolve()
    assert settings.seed_path == (ROOT / "fixtures/demo/memories.json").resolve()


def test_cloud_api_requires_independent_cookie_and_byok_secrets(tmp_path):
    base = Settings(
        app_env="cloud",
        data_dir=tmp_path,
        database_url="postgresql://unused-in-startup",
    )
    with pytest.raises(RuntimeError, match="PROVIDER_CREDENTIAL_SECRET"):
        create_app(base)

    missing_cookie = Settings(
        **{
            **base.__dict__,
            "provider_credential_secret": "provider-secret-with-entropy",
        },
    )
    with pytest.raises(RuntimeError, match="COOKIE_SECRET"):
        create_app(missing_cookie)
