from __future__ import annotations

import hashlib
import os
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .agent import Aria
from .aria_registry import AriaRegistry
from .architecture import ArchitectureCompiler, ArchitectureStore
from .config import ROOT, Settings
from .context import ContextCompiler
from .db import Database
from .documents import DeclaredDocumentStore
from .embeddings import EmbeddingStore, create_provider
from .models import utc_now
from .retrieval import Retriever
from .store import AppStore
from .toolbox import Toolbox


class Workspace:
    def __init__(self, workspace_id: str, db: Database, settings: Settings):
        self.id = workspace_id
        self.db = db
        provider = create_provider(settings)
        self.embeddings = EmbeddingStore(db, provider)
        self.documents = DeclaredDocumentStore(db, provider)
        self.documents.ingest_tree(settings.document_seed_path, ROOT)
        self.architecture = ArchitectureStore(db, provider)
        self.architecture_compiler = ArchitectureCompiler(self.architecture)
        self.store = AppStore(db)
        self.aria_registry = AriaRegistry(db)
        self.retriever = Retriever(db, self.embeddings)
        self.context = ContextCompiler(settings, self.retriever, self.documents)
        self.toolbox = Toolbox(
            db, self.context, settings.aria_deep_model, self.architecture_compiler,
            settings.aria_tour_model,
        )
        self.aria = Aria(
            settings, db, self.store, self.retriever, self.context,
            self.architecture_compiler,
        )


class Workspaces:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.items: dict[str, Workspace] = {}
        if settings.cloud and not settings.database_url:
            raise RuntimeError(
                "Cloud mode requires DATABASE_URL; instance-local SQLite is not durable"
            )
        base = (
            Path(os.getenv("TMPDIR", "/tmp")) / "command-center-v3"
            if settings.cloud
            else settings.data_dir
        )
        self.directory = base / "workspaces"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.dev_workspace_marker = base / "dev-workspace-id"

    @staticmethod
    def valid_workspace_id(workspace_id: str) -> bool:
        return bool(re.fullmatch(r"ws_[0-9a-f]{16}", workspace_id))

    def _existing_workspace_ids(self) -> list[str]:
        if self.settings.database_url:
            return []
        return sorted(
            path.stem for path in self.directory.glob("ws_*.db")
            if self.valid_workspace_id(path.stem)
        )

    def _read_dev_workspace_marker(self) -> str | None:
        if not self.dev_workspace_marker.exists():
            return None
        workspace_id = self.dev_workspace_marker.read_text(encoding="utf-8").strip()
        if not self.valid_workspace_id(workspace_id):
            raise RuntimeError("The local development workspace marker is invalid")
        if not self.settings.database_url and not (
            self.directory / f"{workspace_id}.db"
        ).exists():
            raise RuntimeError("The local development workspace database is missing")
        return workspace_id

    def _persist_dev_workspace(self, workspace_id: str) -> str:
        self.dev_workspace_marker.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(
                self.dev_workspace_marker,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError:
            return self._read_dev_workspace_marker() or workspace_id
        with os.fdopen(descriptor, "w", encoding="utf-8") as marker:
            marker.write(f"{workspace_id}\n")
        return workspace_id

    def resolve_dev_workspace(self, authenticated_workspace_id: str | None = None) -> str:
        """Resolve one persisted local workspace without guessing among databases."""
        configured = self.settings.dev_workspace_id
        if configured:
            if not self.valid_workspace_id(configured):
                raise RuntimeError(
                    "COMMAND_CENTER_DEV_WORKSPACE_ID must match ws_<16 lowercase hex>"
                )
            existing = self._existing_workspace_ids()
            if existing and configured not in existing:
                raise RuntimeError(
                    "COMMAND_CENTER_DEV_WORKSPACE_ID does not name an existing local workspace"
                )
            marked = self._read_dev_workspace_marker()
            if marked and marked != configured:
                raise RuntimeError(
                    "COMMAND_CENTER_DEV_WORKSPACE_ID conflicts with the persisted local workspace"
                )
            return self._persist_dev_workspace(configured)

        marked = self._read_dev_workspace_marker()
        if marked:
            return marked
        if authenticated_workspace_id:
            if not self.valid_workspace_id(authenticated_workspace_id):
                raise RuntimeError("Authenticated workspace identifier is invalid")
            return self._persist_dev_workspace(authenticated_workspace_id)

        existing = self._existing_workspace_ids()
        if len(existing) == 1:
            return self._persist_dev_workspace(existing[0])
        if not existing:
            return self._persist_dev_workspace("ws_0000000000000000")
        raise RuntimeError(
            "Multiple local workspaces exist. Open the previously authenticated browser "
            "once or set COMMAND_CENTER_DEV_WORKSPACE_ID to the intended workspace."
        )

    def get(self, workspace_id: str) -> Workspace:
        if workspace_id not in self.items:
            if self.settings.database_url:
                from .postgres import PostgresDatabase

                db = PostgresDatabase(
                    self.settings.database_url, workspace_id, self.settings.seed_path,
                )
            else:
                db = Database(
                    self.directory / f"{workspace_id}.db", self.settings.seed_path,
                )
            workspace = Workspace(workspace_id, db, self.settings)
            if workspace.embeddings.status().pending:
                workspace.embeddings.sync()
            self.items[workspace_id] = workspace
        return self.items[workspace_id]

    def create_pair_code(self, workspace_id: str) -> str:
        code = f"{workspace_id}.{secrets.token_hex(8).upper()}"
        expires = (
            datetime.now(UTC) + timedelta(minutes=5)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        with self.get(workspace_id).db.transaction() as conn:
            conn.execute(
                "DELETE FROM pair_codes WHERE expires_at<=? OR consumed_at IS NOT NULL",
                (utc_now(),),
            )
            conn.execute(
                "INSERT INTO pair_codes VALUES(?,?,?,NULL)",
                (self.token_hash(code), utc_now(), expires),
            )
        return code

    def consume_pair_code(self, code: str) -> str | None:
        workspace_id, marker, _ = code.partition(".")
        if not marker or not workspace_id.startswith("ws_"):
            return None
        workspace = self.get(workspace_id)
        digest, now = self.token_hash(code), utc_now()
        with workspace.db.transaction() as conn:
            found = conn.execute(
                """SELECT 1 FROM pair_codes WHERE code_hash=?
                AND consumed_at IS NULL AND expires_at>?""", (digest, now),
            ).fetchone()
            if not found:
                return None
            conn.execute(
                "UPDATE pair_codes SET consumed_at=? WHERE code_hash=?",
                (now, digest),
            )
        return workspace_id

    @staticmethod
    def token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def create_workspace_token(
        self, workspace_id: str, label: str = "paired client",
    ) -> tuple[str, str]:
        token_id = f"tok_{uuid.uuid4().hex[:16]}"
        token = f"ccw_{workspace_id}." + secrets.token_urlsafe(32)
        with self.get(workspace_id).db.transaction() as conn:
            conn.execute(
                "INSERT INTO workspace_tokens VALUES(?,?,?,?,NULL)",
                (token_id, self.token_hash(token), label, utc_now()),
            )
        return token_id, token

    def resolve_workspace_token(self, token: str | None) -> str | None:
        if not token:
            return None
        digest = self.token_hash(token)
        encoded_workspace = token.split(".", 1)[0].removeprefix("ccw_")
        workspace_ids = (
            {encoded_workspace}
            if re.fullmatch(r"ws_[0-9a-f]{16}", encoded_workspace)
            else set(self.items)
        )
        if not self.settings.database_url and not workspace_ids:
            workspace_ids.update(path.stem for path in self.directory.glob("ws_*.db"))
        for workspace_id in workspace_ids:
            workspace = self.get(workspace_id)
            with workspace.db.connect() as conn:
                found = conn.execute(
                    """SELECT 1 FROM workspace_tokens
                    WHERE token_hash=? AND revoked_at IS NULL""", (digest,),
                ).fetchone()
            if found:
                return workspace_id
        return None
