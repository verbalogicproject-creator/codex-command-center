from __future__ import annotations

import base64
import binascii
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from cryptography.fernet import Fernet, InvalidToken


OPENAI_CREDENTIAL_COOKIE = "cc3_openai_byok"


def _iso_timestamp(timestamp: int) -> str:
    return (
        datetime.fromtimestamp(timestamp, UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


@dataclass(frozen=True)
class ProviderCredential:
    api_key: str
    expires_at: str


class ProviderCredentialVault:
    """Authenticated, expiring browser-session envelopes for user-owned keys."""

    def __init__(self, secret: str, ttl_seconds: int):
        if ttl_seconds < 60:
            raise ValueError("provider credential TTL must be at least 60 seconds")
        key = hashlib.sha256(
            f"command-center-provider-credentials-v1:{secret}".encode()
        ).digest()
        self.fernet = Fernet(base64.urlsafe_b64encode(key))
        self.ttl_seconds = ttl_seconds

    def seal(
        self, workspace_id: str, api_key: str, *, now: int | None = None,
    ) -> tuple[str, ProviderCredential]:
        issued_at = int(time.time()) if now is None else now
        expires_at = issued_at + self.ttl_seconds
        payload = json.dumps({
            "version": 1,
            "provider": "openai",
            "workspace_id": workspace_id,
            "api_key": api_key,
            "expires_at": expires_at,
        }, separators=(",", ":")).encode()
        token = self.fernet.encrypt_at_time(payload, issued_at).decode()
        return token, ProviderCredential(
            api_key=api_key, expires_at=_iso_timestamp(expires_at),
        )

    def open(
        self, token: str | None, workspace_id: str, *, now: int | None = None,
    ) -> ProviderCredential | None:
        if not token:
            return None
        current_time = int(time.time()) if now is None else now
        try:
            encoded = token.encode("ascii")
            decoded = base64.b64decode(
                encoded, altchars=b"-_", validate=True,
            )
            if base64.urlsafe_b64encode(decoded) != encoded:
                return None
            raw = self.fernet.decrypt_at_time(
                encoded, ttl=self.ttl_seconds, current_time=current_time,
            )
            payload = json.loads(raw)
        except (
            InvalidToken, ValueError, TypeError, UnicodeEncodeError,
            binascii.Error, json.JSONDecodeError,
        ):
            return None
        if (
            payload.get("version") != 1
            or payload.get("provider") != "openai"
            or payload.get("workspace_id") != workspace_id
            or not isinstance(payload.get("api_key"), str)
            or not isinstance(payload.get("expires_at"), int)
            or payload["expires_at"] <= current_time
        ):
            return None
        return ProviderCredential(
            api_key=payload["api_key"],
            expires_at=_iso_timestamp(payload["expires_at"]),
        )
