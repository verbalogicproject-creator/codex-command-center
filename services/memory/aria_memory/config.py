from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "local")
    data_dir: Path = Path(os.getenv("DATA_DIR", ROOT / "data"))
    seed_path: Path = Path(
        os.getenv("DEMO_SEED", ROOT / "fixtures" / "demo" / "memories.json")
    )
    demo_access_code: str = os.getenv("DEMO_ACCESS_CODE", "command-center")
    cookie_secret: str = os.getenv(
        "COOKIE_SECRET", "local-development-secret-change-before-deploy"
    )
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    aria_model: str = os.getenv("ARIA_MODEL", "gpt-5.6-terra")
    aria_deep_model: str = os.getenv("ARIA_DEEP_MODEL", "gpt-5.6-sol")
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "hash")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
    embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "256"))
    max_aria_turns: int = int(os.getenv("MAX_ARIA_TURNS", "20"))
    max_direct_recalls: int = int(os.getenv("MAX_DIRECT_RECALLS", "100"))

    @property
    def cloud(self) -> bool:
        return self.app_env == "cloud"

