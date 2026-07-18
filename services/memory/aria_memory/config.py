from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def env_path(name: str, fallback: Path) -> Path:
    value = Path(os.getenv(name, str(fallback))).expanduser()
    return value if value.is_absolute() else (ROOT / value).resolve()


@dataclass(frozen=True)
class Settings:
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "local"))
    data_dir: Path = field(default_factory=lambda: env_path("DATA_DIR", ROOT / "data"))
    seed_path: Path = field(default_factory=lambda: env_path(
        "DEMO_SEED", ROOT / "fixtures" / "demo" / "memories.json"
    ))
    demo_access_code: str = field(
        default_factory=lambda: os.getenv("DEMO_ACCESS_CODE", "command-center")
    )
    cookie_secret: str = field(default_factory=lambda: os.getenv(
        "COOKIE_SECRET", "local-development-secret-change-before-deploy"
    ))
    openai_api_key: str | None = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY")
    )
    aria_model: str = field(
        default_factory=lambda: os.getenv("ARIA_MODEL", "gpt-5.6-terra")
    )
    aria_deep_model: str = field(
        default_factory=lambda: os.getenv("ARIA_DEEP_MODEL", "gpt-5.6-sol")
    )
    embedding_provider: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "hash")
    )
    embedding_model: str = field(default_factory=lambda: os.getenv(
        "EMBEDDING_MODEL", "text-embedding-3-large"
    ))
    embedding_dimensions: int = field(
        default_factory=lambda: int(os.getenv("EMBEDDING_DIMENSIONS", "256"))
    )
    max_aria_turns: int = field(
        default_factory=lambda: int(os.getenv("MAX_ARIA_TURNS", "20"))
    )
    max_direct_recalls: int = field(
        default_factory=lambda: int(os.getenv("MAX_DIRECT_RECALLS", "100"))
    )

    @property
    def cloud(self) -> bool:
        return self.app_env == "cloud"
