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
    database_url: str | None = field(default_factory=lambda: os.getenv("DATABASE_URL"))
    seed_path: Path = field(default_factory=lambda: env_path(
        "DEMO_SEED", ROOT / "fixtures" / "demo" / "memories.json"
    ))
    document_seed_path: Path = field(default_factory=lambda: env_path(
        "DEMO_DOCUMENTS", ROOT / "fixtures" / "demo" / "documents"
    ))
    demo_access_code: str = field(
        default_factory=lambda: os.getenv("DEMO_ACCESS_CODE", "command-center")
    )
    cookie_secret: str = field(default_factory=lambda: os.getenv(
        "COOKIE_SECRET", "local-development-secret-change-before-deploy"
    ))
    provider_credential_secret: str | None = field(
        default_factory=lambda: os.getenv("PROVIDER_CREDENTIAL_SECRET")
    )
    provider_credential_ttl_seconds: int = field(
        default_factory=lambda: int(os.getenv(
            "PROVIDER_CREDENTIAL_TTL_SECONDS", "3600"
        ))
    )
    embedding_api_key: str | None = field(
        default_factory=lambda: os.getenv("EMBEDDING_API_KEY")
    )
    aria_model: str = field(
        default_factory=lambda: os.getenv("ARIA_MODEL", "gpt-5.6-terra")
    )
    aria_deep_model: str = field(
        default_factory=lambda: os.getenv("ARIA_DEEP_MODEL", "gpt-5.6-sol")
    )
    realtime_model: str = field(
        default_factory=lambda: os.getenv("ARIA_REALTIME_MODEL", "gpt-realtime-2.1")
    )
    realtime_voice: str = field(
        default_factory=lambda: os.getenv("ARIA_REALTIME_VOICE", "marin")
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
    max_voice_sessions: int = field(
        default_factory=lambda: int(os.getenv("MAX_VOICE_SESSIONS", "40"))
    )

    @property
    def cloud(self) -> bool:
        return self.app_env == "cloud"

    @property
    def credential_secret(self) -> str:
        return self.provider_credential_secret or self.cookie_secret
