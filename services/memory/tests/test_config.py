from aria_memory.config import ROOT, Settings


def test_relative_env_paths_resolve_from_repository_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATA_DIR", "./data")
    monkeypatch.setenv("DEMO_SEED", "./fixtures/demo/memories.json")

    settings = Settings()

    assert settings.data_dir == (ROOT / "data").resolve()
    assert settings.seed_path == (ROOT / "fixtures/demo/memories.json").resolve()
