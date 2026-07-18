from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .agent import Aria
from .architecture import (
    ArchitectureCompiler,
    ArchitectureStore,
    build_architecture_health,
    parse_architecture_document,
)
from .architecture.manifest import MAX_CORPUS_BYTES
from .architecture.parser import MAX_DOCUMENT_BYTES
from .architecture.models import (
    ArchitectureBrief,
    ArchitectureBriefRequest,
    ArchitectureCheckRequest,
    ArchitectureHealth,
    ArchitectureLintRequest,
    ArchitectureLintResponse,
    ArchitectureSyncRequest,
    ArchitectureSyncResponse,
)
from .config import ROOT, Settings
from .context import ContextCompiler
from .db import Database
from .documents import DeclaredDocumentStore
from .embeddings import EmbeddingStore, create_provider
from .models import (
    AuditResponse, AuthResponse, Capability, CapabilityInput, CapabilityList,
    CapabilityRecommendationRequest, CapabilityRecommendations,
    ChatRequest, DemoAuthRequest, ErrorDetail,
    ContextPack, ContextPackRequest, DocumentRecallRequest, DocumentRecallResponse,
    ErrorResponse, GraphEdge, GraphNode, GraphResponse, HookEventRequest,
    Handoff, HandoffDraftRequest, HandoffList, HandoffLoadRequest, HandoffPacket,
    HandoffUpdateRequest, HookEventResponse, PairAuthRequest, PairStartResponse,
    Proposal, ProposalCreate, ScreenshotAnalysis, ScreenshotAnalyzeRequest,
    ProposalList, RecallRequest, RecallResponse, Session,
    SessionCreate, SessionList, StatusResponse, SyncResponse, TimelineResponse,
    TurnList,
)
from .mcp import handle_rpc
from .retrieval import Retriever
from .store import AppStore
from .toolbox import Toolbox

COOKIE_NAME = "cc3_workspace"


class Workspace:
    def __init__(self, workspace_id: str, db: Database, settings: Settings):
        self.id = workspace_id
        self.db = db
        provider = create_provider(settings)
        self.embeddings = EmbeddingStore(db, provider)
        self.documents = DeclaredDocumentStore(db, provider)
        self.documents.ingest_tree(settings.document_seed_path, ROOT)
        self.architecture = ArchitectureStore(db)
        self.architecture_compiler = ArchitectureCompiler(self.architecture)
        self.store = AppStore(db)
        self.retriever = Retriever(db, self.embeddings)
        self.context = ContextCompiler(settings, self.retriever, self.documents)
        self.toolbox = Toolbox(
            db, self.context, settings.aria_deep_model, settings.openai_api_key,
            self.architecture_compiler,
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
        base = Path("/tmp/command-center-v3") if settings.cloud else settings.data_dir
        self.directory = base / "workspaces"
        self.directory.mkdir(parents=True, exist_ok=True)

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
        from .models import utc_now

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
        from .models import utc_now

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
        from .models import utc_now

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


def sign(workspace_id: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), workspace_id.encode(), hashlib.sha256).hexdigest()
    return f"{workspace_id}.{digest}"


def verify(value: str | None, secret: str) -> str | None:
    if not value or "." not in value:
        return None
    workspace_id, _ = value.rsplit(".", 1)
    return workspace_id if hmac.compare_digest(value, sign(workspace_id, secret)) else None


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    workspaces = Workspaces(settings)
    app = FastAPI(
        title="Command Center v3", version="0.1.0",
        responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    )
    if not settings.cloud:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.state.settings = settings
    app.state.workspaces = workspaces

    @app.middleware("http")
    async def structured_request_log(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        if settings.cloud:
            logging.getLogger("command_center.request").info(json.dumps({
                "event": "http_request", "method": request.method,
                "path": request.url.path, "status": response.status_code,
                "duration_ms": round(
                    (time.perf_counter() - started) * 1000, 2
                ),
            }, separators=(",", ":")))
        return response

    def current_workspace(
        token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
        command_token: Annotated[
            str | None, Header(alias="X-Command-Center-Token")
        ] = None,
    ) -> Workspace:
        workspace_id = (
            workspaces.resolve_workspace_token(command_token)
            or verify(token, settings.cookie_secret)
        )
        if not workspace_id:
            raise HTTPException(401, detail={"code": "unauthorized", "message": "Sign in required"})
        return workspaces.get(workspace_id)

    def limited(workspace: Workspace, category: str, maximum: int) -> None:
        cutoff = (
            datetime.now(UTC) - timedelta(hours=24)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        with workspace.db.transaction() as conn:
            count = conn.execute(
                """SELECT COUNT(*) FROM quota_events WHERE category=?
                AND created_at >= ?""", (category, cutoff)
            ).fetchone()[0]
            if count >= maximum:
                raise HTTPException(429, detail={
                    "code": "quota_exceeded", "message": f"{category} daily limit reached"
                })
            from .models import utc_now

            conn.execute("INSERT INTO quota_events VALUES(?,?,?)",
                         (f"quota_{uuid.uuid4().hex}", category, utc_now()))

    @app.post("/api/v1/auth/demo", response_model=AuthResponse)
    def auth_demo(body: DemoAuthRequest, response: Response) -> AuthResponse:
        if not hmac.compare_digest(body.code, settings.demo_access_code):
            raise HTTPException(401, detail={"code": "invalid_code", "message": "Invalid demo code"})
        workspace_id = f"ws_{uuid.uuid4().hex[:16]}"
        workspaces.get(workspace_id)
        response.set_cookie(
            COOKIE_NAME, sign(workspace_id, settings.cookie_secret),
            httponly=True, secure=settings.cloud, samesite="lax", max_age=86400,
        )
        return AuthResponse(authenticated=True, workspace_id=workspace_id)

    @app.post("/api/v1/auth/token/revoke")
    def revoke_token(
        command_token: Annotated[
            str | None, Header(alias="X-Command-Center-Token")
        ] = None,
        workspace: Workspace = Depends(current_workspace),
    ):
        if not command_token:
            raise HTTPException(422, "token header is required")
        from .models import utc_now

        with workspace.db.transaction() as conn:
            changed = conn.execute(
                "UPDATE workspace_tokens SET revoked_at=? WHERE token_hash=?",
                (utc_now(), workspaces.token_hash(command_token)),
            ).rowcount
        return {"revoked": bool(changed)}

    @app.post("/api/v1/auth/pair/start", response_model=PairStartResponse)
    def start_pair(
        workspace: Workspace = Depends(current_workspace),
    ) -> PairStartResponse:
        return PairStartResponse(
            code=workspaces.create_pair_code(workspace.id),
            expires_in_seconds=300,
        )

    @app.post("/api/v1/auth/pair", response_model=AuthResponse)
    def finish_pair(body: PairAuthRequest, response: Response) -> AuthResponse:
        workspace_id = workspaces.consume_pair_code(body.code)
        if not workspace_id:
            raise HTTPException(401, detail={
                "code": "invalid_pair_code",
                "message": "Pairing code is invalid or expired",
            })
        response.set_cookie(
            COOKIE_NAME, sign(workspace_id, settings.cookie_secret),
            httponly=True, secure=settings.cloud, samesite="lax", max_age=86400,
        )
        token_id, workspace_token = workspaces.create_workspace_token(workspace_id)
        return AuthResponse(
            authenticated=True, workspace_id=workspace_id,
            workspace_token=workspace_token, token_id=token_id,
        )

    @app.get("/api/v1/capabilities", response_model=CapabilityList)
    def capabilities(
        query: str = "", kind: str | None = None, repository: str | None = None,
        trusted_only: bool = True,
        workspace: Workspace = Depends(current_workspace),
    ) -> CapabilityList:
        return CapabilityList(items=workspace.toolbox.list_capabilities(
            query=query, kind=kind, repository=repository, trusted_only=trusted_only,
        ))

    @app.post(
        "/api/v1/capabilities/recommend",
        response_model=CapabilityRecommendations,
    )
    def recommend_capabilities(
        body: CapabilityRecommendationRequest,
        workspace: Workspace = Depends(current_workspace),
    ) -> CapabilityRecommendations:
        return workspace.toolbox.recommend(body)

    @app.post("/api/v1/capabilities", response_model=Capability, status_code=201)
    def create_capability(
        body: CapabilityInput, workspace: Workspace = Depends(current_workspace),
    ) -> Capability:
        return workspace.toolbox.create_capability(body)

    @app.get("/api/v1/capabilities/{capability_id}", response_model=Capability)
    def get_capability(
        capability_id: str, version: int | None = None,
        workspace: Workspace = Depends(current_workspace),
    ) -> Capability:
        item = workspace.toolbox.get_capability(capability_id, version)
        if not item:
            raise HTTPException(404, "capability not found")
        return item

    @app.post("/api/v1/screenshots/analyze", response_model=ScreenshotAnalysis)
    def analyze_screenshot(
        body: ScreenshotAnalyzeRequest,
        workspace: Workspace = Depends(current_workspace),
    ) -> ScreenshotAnalysis:
        limited(workspace, "screenshot", 40)
        try:
            return workspace.toolbox.analyze_screenshot(body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get("/api/v1/handoffs", response_model=HandoffList)
    def handoffs(workspace: Workspace = Depends(current_workspace)) -> HandoffList:
        return HandoffList(items=workspace.toolbox.list_handoffs())

    @app.post("/api/v1/handoffs/load", response_model=HandoffPacket)
    def load_handoff(
        body: HandoffLoadRequest,
        workspace: Workspace = Depends(current_workspace),
    ) -> HandoffPacket:
        try:
            return workspace.toolbox.load_handoff(body)
        except KeyError:
            raise HTTPException(404, "published handoff not found") from None
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None

    @app.post("/api/v1/handoffs", response_model=Handoff, status_code=201)
    def create_handoff(
        body: HandoffDraftRequest,
        workspace: Workspace = Depends(current_workspace),
    ) -> Handoff:
        try:
            return workspace.toolbox.create_handoff(body, "browser")
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get("/api/v1/handoffs/{handoff_id}", response_model=Handoff)
    def get_handoff(
        handoff_id: str, workspace: Workspace = Depends(current_workspace),
    ) -> Handoff:
        item = workspace.toolbox.get_handoff(handoff_id)
        if not item:
            raise HTTPException(404, "handoff not found")
        return item

    @app.patch("/api/v1/handoffs/{handoff_id}", response_model=Handoff)
    def update_handoff(
        handoff_id: str, body: HandoffUpdateRequest,
        workspace: Workspace = Depends(current_workspace),
    ) -> Handoff:
        try:
            return workspace.toolbox.update_handoff(handoff_id, body)
        except KeyError:
            raise HTTPException(404, "handoff not found") from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.post("/api/v1/handoffs/{handoff_id}/versions", response_model=Handoff)
    def version_handoff(
        handoff_id: str, body: HandoffUpdateRequest,
        workspace: Workspace = Depends(current_workspace),
    ) -> Handoff:
        try:
            return workspace.toolbox.new_handoff_version(handoff_id, body, "browser")
        except KeyError:
            raise HTTPException(404, "handoff not found") from None

    @app.post("/api/v1/handoffs/{handoff_id}/publish", response_model=Handoff)
    def publish_handoff(
        handoff_id: str, workspace: Workspace = Depends(current_workspace),
    ) -> Handoff:
        try:
            return workspace.toolbox.publish_handoff(handoff_id)
        except KeyError:
            raise HTTPException(404, "handoff not found") from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.post("/api/v1/handoffs/{handoff_id}/revoke", response_model=Handoff)
    def revoke_handoff(
        handoff_id: str, workspace: Workspace = Depends(current_workspace),
    ) -> Handoff:
        try:
            return workspace.toolbox.revoke_handoff(handoff_id)
        except KeyError:
            raise HTTPException(404, "handoff not found") from None

    @app.post("/mcp")
    async def mcp_endpoint(
        request: Request, workspace: Workspace = Depends(current_workspace),
    ):
        from fastapi.responses import JSONResponse

        try:
            message = await request.json()
        except ValueError:
            raise HTTPException(400, "invalid JSON-RPC body") from None
        if isinstance(message, list):
            result = [
                response for item in message
                if (response := handle_rpc(workspace, item)) is not None
            ]
        else:
            result = handle_rpc(workspace, message)
        if result is None:
            return Response(status_code=202)
        return JSONResponse(
            result, headers={"MCP-Protocol-Version": "2025-06-18"},
        )

    @app.get("/.well-known/oauth-authorization-server")
    @app.get("/.well-known/oauth-protected-resource")
    def oauth_metadata_not_configured():
        raise HTTPException(404, detail={
            "code": "oauth_metadata_unavailable",
            "message": "Use the Command Center one-time browser pairing flow.",
        })

    @app.get("/api/v1/status", response_model=StatusResponse)
    def status(workspace: Workspace = Depends(current_workspace)) -> StatusResponse:
        embedding = workspace.embeddings.status()
        with workspace.db.connect() as conn:
            pending = conn.execute(
                "SELECT COUNT(*) FROM proposals WHERE status='pending'"
            ).fetchone()[0]
        return StatusResponse(
            memories=workspace.db.count("memories"), documents=workspace.db.count("documents"),
            sessions=workspace.db.count("sessions"),
            proposals_pending=pending, embeddings=embedding,
            aria_model=settings.aria_model, deep_model=settings.aria_deep_model,
            degraded=(
                embedding.degraded or workspace.documents.degraded
                or not bool(settings.openai_api_key)
            ),
        )

    @app.post("/api/v1/recall", response_model=RecallResponse)
    def recall(body: RecallRequest,
               workspace: Workspace = Depends(current_workspace)) -> RecallResponse:
        limited(workspace, "recall", settings.max_direct_recalls)
        return workspace.retriever.recall(body)

    @app.post("/api/v1/documents/recall", response_model=DocumentRecallResponse)
    def recall_documents(
        body: DocumentRecallRequest,
        workspace: Workspace = Depends(current_workspace),
    ) -> DocumentRecallResponse:
        limited(workspace, "recall", settings.max_direct_recalls)
        return workspace.documents.recall(body)

    @app.post(
        "/api/v1/architecture/lint",
        response_model=ArchitectureLintResponse,
    )
    def lint_architecture(
        body: ArchitectureLintRequest,
        workspace: Workspace = Depends(current_workspace),
    ) -> ArchitectureLintResponse:
        del workspace  # Authentication is required; lint itself is stateless.
        document_sizes = [
            len(document.content.encode("utf-8")) for document in body.documents
        ]
        if max(document_sizes) > MAX_DOCUMENT_BYTES or sum(document_sizes) > MAX_CORPUS_BYTES:
            raise HTTPException(413, detail={
                "code": "architecture_corpus_too_large",
                "message": "Architecture lint input exceeds the declared size bounds.",
            })
        parsed = [
            parse_architecture_document(
                document.content,
                document.source_uri,
                repository=body.repository.name,
            )
            for document in body.documents
        ]
        issues = ArchitectureStore._validation_issues(
            body.repository.name, parsed,
        )
        corpus_surface = json.dumps(sorted(
            (item.source_uri, item.content_hash) for item in parsed
        ), separators=(",", ":"))
        valid_cards = sum(item.valid for item in parsed)
        return ArchitectureLintResponse(
            valid=valid_cards > 0 and not any(
                issue.severity == "error" for issue in issues
            ),
            document_count=len(parsed),
            valid_cards=valid_cards,
            coverage=valid_cards / len(parsed),
            corpus_hash=hashlib.sha256(corpus_surface.encode()).hexdigest(),
            issues=issues,
        )

    @app.post(
        "/api/v1/architecture/sync",
        response_model=ArchitectureSyncResponse,
    )
    def sync_architecture(
        body: ArchitectureSyncRequest,
        workspace: Workspace = Depends(current_workspace),
    ) -> ArchitectureSyncResponse:
        total_bytes = sum(
            len(document.content.encode("utf-8")) for document in body.documents
        )
        if (
            total_bytes > MAX_CORPUS_BYTES
            or any(
                len(document.content.encode("utf-8")) > MAX_DOCUMENT_BYTES
                for document in body.documents
            )
        ):
            raise HTTPException(413, detail={
                "code": "architecture_corpus_too_large",
                "message": f"Architecture corpus exceeds {MAX_CORPUS_BYTES} bytes.",
            })
        parsed = [
            parse_architecture_document(
                document.content,
                document.source_uri,
                repository=body.repository.name,
            )
            for document in body.documents
        ]
        snapshot = workspace.architecture.activate(
            repository=body.repository.name,
            repository_id=body.repository.id,
            aliases=body.repository.aliases,
            documents=parsed,
            source_revision=body.source_revision,
            manifest_hash=body.manifest_hash,
        )
        return ArchitectureSyncResponse(
            snapshot=snapshot,
            health=build_architecture_health(
                workspace.architecture,
                body.repository.id,
                snapshot_id=snapshot.id,
            ),
        )

    @app.post(
        "/api/v1/architecture/check",
        response_model=ArchitectureHealth,
    )
    def check_architecture(
        body: ArchitectureCheckRequest,
        workspace: Workspace = Depends(current_workspace),
    ) -> ArchitectureHealth:
        return build_architecture_health(
            workspace.architecture,
            body.repository,
            local_documents=body.documents,
            local_revision=body.source_revision,
            manifest_hash=body.manifest_hash,
        )

    @app.get(
        "/api/v1/architecture/health",
        response_model=ArchitectureHealth,
    )
    def architecture_health(
        repository: str = Query(min_length=1, max_length=240),
        workspace: Workspace = Depends(current_workspace),
    ) -> ArchitectureHealth:
        return build_architecture_health(workspace.architecture, repository)

    @app.post(
        "/api/v1/architecture/brief",
        response_model=ArchitectureBrief,
    )
    def architecture_brief(
        body: ArchitectureBriefRequest,
        workspace: Workspace = Depends(current_workspace),
    ) -> ArchitectureBrief:
        limited(workspace, "recall", settings.max_direct_recalls)
        return workspace.architecture_compiler.build(body)

    @app.get("/api/v1/documents/{document_id}")
    def document(document_id: str, workspace: Workspace = Depends(current_workspace)):
        item = workspace.documents.get(document_id)
        if not item:
            raise HTTPException(404, "document not found")
        return item

    @app.post("/api/v1/context/pack", response_model=ContextPack)
    def context_pack(
        body: ContextPackRequest,
        workspace: Workspace = Depends(current_workspace),
    ) -> ContextPack:
        limited(workspace, "recall", settings.max_direct_recalls)
        return workspace.context.build(body)

    @app.post("/api/v1/realtime/token")
    async def realtime_token(
        workspace: Workspace = Depends(current_workspace),
    ):
        """Mint a short-lived browser token without exposing the standard API key."""
        if not settings.openai_api_key:
            raise HTTPException(503, detail={
                "code": "voice_unavailable",
                "message": "Aria voice needs an OpenAI API key on the server.",
            })
        limited(workspace, "voice", settings.max_voice_sessions)
        safety_id = hashlib.sha256(workspace.id.encode()).hexdigest()[:64]
        session = {
            "expires_after": {"anchor": "created_at", "seconds": 600},
            "session": {
                "type": "realtime",
                "model": settings.realtime_model,
                "instructions": (
                    "You are Aria, the concise voice guide for Command Center. "
                    "Use declared UI tools for interface actions. You may create only "
                    "pending proposals; durable memory always requires a browser tap."
                ),
                "max_output_tokens": 700,
                "audio": {
                    "input": {
                        "transcription": {"model": "gpt-4o-mini-transcribe"},
                        "turn_detection": {
                            "type": "server_vad",
                            "create_response": True,
                            "interrupt_response": True,
                        },
                    },
                    "output": {"voice": settings.realtime_voice},
                },
            },
        }
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                upstream = await client.post(
                    "https://api.openai.com/v1/realtime/client_secrets",
                    headers={
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "Content-Type": "application/json",
                        "OpenAI-Safety-Identifier": safety_id,
                    },
                    json=session,
                )
        except httpx.HTTPError as exc:
            raise HTTPException(502, detail={
                "code": "voice_upstream_unavailable",
                "message": "Could not reach the realtime voice service.",
                "retryable": True,
            }) from exc
        if upstream.status_code != 200:
            raise HTTPException(502, detail={
                "code": "voice_session_failed",
                "message": "The realtime voice service refused the session.",
                "retryable": upstream.status_code >= 500,
            })
        return upstream.json()

    @app.get("/api/v1/memories/{table}/{memory_id}")
    def memory(table: str, memory_id: str,
               workspace: Workspace = Depends(current_workspace)):
        if table not in {"episodes", "facts"}:
            raise HTTPException(404, "memory table not found")
        item = workspace.db.get_memory(memory_id)
        expected = table[:-1]
        if not item or item.entity_type != expected:
            raise HTTPException(404, "memory not found")
        return item

    @app.get("/api/v1/timeline", response_model=TimelineResponse)
    def timeline(workspace: Workspace = Depends(current_workspace),
                 project: str | None = None, kind: list[str] = Query(default=[]),
                 limit: int = Query(default=50, ge=1, le=200)) -> TimelineResponse:
        items = workspace.db.list_memories(project, kind)
        items.sort(key=lambda item: item.happened_at, reverse=True)
        return TimelineResponse(items=items[:limit])

    @app.get("/api/v1/graph", response_model=GraphResponse)
    def graph(workspace: Workspace = Depends(current_workspace)) -> GraphResponse:
        memories = workspace.db.list_memories()
        documents = workspace.documents.list()
        architecture_repositories = workspace.architecture.list_repositories()
        projects = sorted(
            {m.project for m in memories}
            | {document.repository for document in documents}
            | {repository.name for repository in architecture_repositories}
        )
        nodes = [GraphNode(
            id=f"project:{p}", type="repository", label=p, project=p, status="active",
            stage="repository",
        ) for p in projects]
        nodes += [GraphNode(
            id=m.id, type=("decision" if m.kind == "decision" else m.entity_type),
            label=m.title, project=m.project, status=m.status, evidence_id=m.id,
            stage="durable",
        ) for m in memories]
        nodes += [GraphNode(
            id=document.id, type="document", label=document.title,
            project=document.repository, status=document.status,
            evidence_id=document.id, stage="declared",
        ) for document in documents]
        architecture_documents = []
        architecture_edges = []
        architecture_snapshot_repositories: dict[str, str] = {}
        for repository in architecture_repositories:
            snapshot = workspace.architecture.active_snapshot(repository.id)
            if not snapshot:
                continue
            architecture_snapshot_repositories[snapshot.id] = repository.name
            versions = workspace.architecture.list_document_versions(snapshot.id)
            architecture_documents.extend(versions)
            architecture_edges.extend(workspace.architecture.list_edges(snapshot.id))
            nodes += [GraphNode(
                id=document.id,
                type=str(document.declaration.get("kind") or "architecture_doc"),
                label=document.title,
                project=repository.name,
                status=str(document.declaration.get("status") or "active"),
                evidence_id=document.id,
                stage="declared",
            ) for document in versions]
        capabilities = workspace.toolbox.list_capabilities()
        handoffs = [
            item for item in workspace.toolbox.list_handoffs()
            if item.status == "published"
        ]
        nodes += [GraphNode(
            id=f"capability:{item.stable_id}@{item.version}",
            type="capability", label=f"{item.name} v{item.version}",
            project=(item.repositories[0] if item.repositories else "*"),
            status=item.trust_status, stage="declared",
        ) for item in capabilities]
        nodes += [GraphNode(
            id=f"handoff:{item.id}", type="handoff", label=f"Handoff {item.id}",
            project=item.repository, status=item.status, stage="dense",
        ) for item in handoffs]
        known_node_ids = {node.id for node in nodes}
        for handoff in handoffs:
            for source in handoff.evidence_sources:
                source_id = str(source.get("id") or "")
                if not source_id or source_id in known_node_ids:
                    continue
                if source_id.startswith("adoc_"):
                    document = workspace.architecture.get_document_version(source_id)
                    if document:
                        nodes.append(GraphNode(
                            id=document.id,
                            type=str(
                                document.declaration.get("kind")
                                or "architecture_doc"
                            ),
                            label=document.title,
                            project=handoff.repository,
                            status="pinned",
                            evidence_id=document.id,
                            stage="declared",
                        ))
                        known_node_ids.add(document.id)
                elif source_id.startswith("asec_"):
                    section = workspace.architecture.get_section(source_id)
                    if section:
                        nodes.append(GraphNode(
                            id=section.id,
                            type="architecture_section",
                            label=section.heading,
                            project=handoff.repository,
                            status="pinned",
                            evidence_id=section.id,
                            stage="declared",
                        ))
                        known_node_ids.add(section.id)
        with workspace.db.connect() as conn:
            activations = conn.execute(
                """SELECT handoff_id,client_name,session_id,created_at
                FROM handoff_activations ORDER BY created_at DESC"""
            ).fetchall()
        if activations:
            nodes.append(GraphNode(
                id="client:codex",
                type="client",
                label="Codex",
                project="Command Center",
                status="active",
                stage="dense",
            ))
        edges = [GraphEdge(
            id=f"edge:{m.id}", source=f"project:{m.project}", target=m.id, type="contains"
        ) for m in memories]
        edges += [GraphEdge(
            id=f"edge:{document.id}", source=f"project:{document.repository}",
            target=document.id, type="declares",
        ) for document in documents]
        document_ids = {document.id for document in documents}
        edges += [GraphEdge(
            id=f"dependency:{document.id}:{dependency}", source=document.id,
            target=dependency, type="depends_on",
        ) for document in documents for dependency in document.depends_on
            if dependency in document_ids]
        edges += [GraphEdge(
            id=f"handoff-capability:{handoff.id}:{ref}",
            source=f"capability:{ref}", target=f"handoff:{handoff.id}",
            type="injects",
        ) for handoff in handoffs for ref in handoff.capability_refs]
        edges += [GraphEdge(
            id=f"architecture:{document.id}",
            source=f"project:{architecture_snapshot_repositories[document.snapshot_id]}",
            target=document.id,
            type="declares_version",
        ) for document in architecture_documents]
        edges += [GraphEdge(
            id=edge.id,
            source=edge.source_id,
            target=edge.target_id,
            type=edge.relation_type.casefold(),
        ) for edge in architecture_edges if edge.target_id]
        evidence_links = []
        for handoff in handoffs:
            evidence_links.extend(
                GraphEdge(
                    id=f"handoff-evidence:{handoff.id}:{source.get('id')}",
                    source=str(source.get("id")),
                    target=f"handoff:{handoff.id}",
                    type="selected_for_handoff",
                )
                for source in handoff.evidence_sources if source.get("id")
            )
        edges.extend(evidence_links)
        published_ids = {item.id for item in handoffs}
        edges += [GraphEdge(
            id=f"activation:{row['handoff_id']}:{row['created_at']}",
            source=f"handoff:{row['handoff_id']}",
            target="client:codex",
            type="activated_in_codex",
        ) for row in activations if row["handoff_id"] in published_ids]
        node_by_id = {node.id: node for node in nodes}
        visible_edges = [
            edge for edge in edges
            if edge.source in node_by_id and edge.target in node_by_id
        ]
        return GraphResponse(nodes=list(node_by_id.values()), edges=visible_edges)

    @app.get("/api/v1/sessions", response_model=SessionList)
    def sessions(workspace: Workspace = Depends(current_workspace)) -> SessionList:
        return SessionList(items=workspace.store.sessions())

    @app.post("/api/v1/sessions", response_model=Session, status_code=201)
    def create_session(body: SessionCreate,
                       workspace: Workspace = Depends(current_workspace)) -> Session:
        return workspace.store.create_session(body.title)

    @app.get("/api/v1/sessions/{session_id}/turns", response_model=TurnList)
    def session_turns(session_id: str,
                      workspace: Workspace = Depends(current_workspace)) -> TurnList:
        if not workspace.store.session_exists(session_id):
            raise HTTPException(404, "session not found")
        return TurnList(items=workspace.store.visible_turns(session_id))

    @app.get("/api/v1/sessions/{session_id}/proposals", response_model=ProposalList)
    def session_proposals(
        session_id: str,
        workspace: Workspace = Depends(current_workspace),
    ) -> ProposalList:
        if not workspace.store.session_exists(session_id):
            raise HTTPException(404, "session not found")
        return ProposalList(items=workspace.store.proposals(session_id))

    @app.post("/api/v1/chat/stream")
    async def chat(body: ChatRequest,
                   workspace: Workspace = Depends(current_workspace)):
        if not workspace.store.session_exists(body.session_id):
            raise HTTPException(404, "session not found")
        limited(workspace, "aria", settings.max_aria_turns)

        async def event_stream():
            try:
                for event in await workspace.aria.run(body):
                    yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
            except Exception as exc:
                error = {"code": "chat_failed", "message": str(exc), "retryable": False}
                yield f"event: error\ndata: {json.dumps(error)}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache"})

    @app.post("/api/v1/proposals/{proposal_id}/confirm")
    def confirm(proposal_id: str,
                workspace: Workspace = Depends(current_workspace)):
        try:
            proposal = workspace.store.confirm(proposal_id)
        except KeyError:
            raise HTTPException(404, "proposal not found") from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        workspace.embeddings.sync()
        return proposal

    @app.post("/api/v1/proposals", response_model=Proposal, status_code=201)
    def propose(
        body: ProposalCreate,
        workspace: Workspace = Depends(current_workspace),
    ) -> Proposal:
        if body.session_id and not workspace.store.session_exists(body.session_id):
            raise HTTPException(404, "session not found")
        return workspace.store.create_proposal(
            body.session_id, body.operation, body.payload,
            body.rationale, body.evidence_ids,
        )

    @app.get("/api/v1/proposals", response_model=ProposalList)
    def proposals(
        status: str | None = Query(default=None),
        workspace: Workspace = Depends(current_workspace),
    ) -> ProposalList:
        if status not in {None, "pending", "confirmed", "rejected", "failed"}:
            raise HTTPException(422, "unknown proposal status")
        return ProposalList(items=workspace.store.proposals(status=status))

    @app.post("/api/v1/proposals/{proposal_id}/reject")
    def reject(proposal_id: str,
               workspace: Workspace = Depends(current_workspace)):
        try:
            return workspace.store.reject(proposal_id)
        except KeyError:
            raise HTTPException(404, "proposal not found") from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.get("/api/v1/audit", response_model=AuditResponse)
    def audit(workspace: Workspace = Depends(current_workspace),
              limit: int = Query(default=100, ge=1, le=500)) -> AuditResponse:
        return AuditResponse(items=workspace.store.audit(limit))

    @app.post("/api/v1/hooks/events", response_model=HookEventResponse, status_code=202)
    def hook_event(
        body: HookEventRequest,
        workspace: Workspace = Depends(current_workspace),
    ) -> HookEventResponse:
        return workspace.store.record_hook(body)

    @app.post("/api/v1/index/sync", response_model=SyncResponse)
    def sync(workspace: Workspace = Depends(current_workspace)) -> SyncResponse:
        if settings.cloud:
            raise HTTPException(403, "index sync is local/admin-only")
        workspace.documents.ingest_tree(settings.document_seed_path, ROOT)
        return workspace.embeddings.sync()

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException):
        from fastapi.responses import JSONResponse

        if isinstance(exc.detail, dict) and "code" in exc.detail:
            detail = exc.detail
        else:
            detail = {"code": f"http_{exc.status_code}", "message": str(exc.detail)}
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(error=ErrorDetail(**detail)).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=422,
            content=ErrorResponse(error=ErrorDetail(
                code="validation_error",
                message="; ".join(error["msg"] for error in exc.errors()),
            )).model_dump(),
        )

    web_out = ROOT / "apps" / "web" / "out"
    if web_out.exists():
        assets = web_out / "_next"
        if assets.exists():
            app.mount("/_next", StaticFiles(directory=assets), name="next-assets")

        @app.get("/{path:path}", include_in_schema=False)
        def static_site(path: str):
            requested = (web_out / path).resolve()
            if requested.is_relative_to(web_out.resolve()) and requested.is_file():
                return FileResponse(requested)
            return FileResponse(web_out / "index.html")

    return app


app = create_app()
