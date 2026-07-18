from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .agent import Aria
from .config import ROOT, Settings
from .db import Database
from .embeddings import EmbeddingStore, create_provider
from .models import (
    AuditResponse, AuthResponse, ChatRequest, DemoAuthRequest, ErrorDetail,
    ErrorResponse, GraphEdge, GraphNode, GraphResponse, RecallRequest,
    RecallResponse, Session, SessionCreate, SessionList, StatusResponse,
    SyncResponse, TimelineResponse,
    TurnList,
)
from .retrieval import Retriever
from .store import AppStore

COOKIE_NAME = "cc3_workspace"


class Workspace:
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.embeddings = EmbeddingStore(db, create_provider(settings))
        self.store = AppStore(db)
        self.retriever = Retriever(db, self.embeddings)
        self.aria = Aria(settings, db, self.store, self.retriever)


class Workspaces:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.items: dict[str, Workspace] = {}
        base = Path("/tmp/command-center-v3") if settings.cloud else settings.data_dir
        self.directory = base / "workspaces"
        self.directory.mkdir(parents=True, exist_ok=True)

    def get(self, workspace_id: str) -> Workspace:
        if workspace_id not in self.items:
            db = Database(self.directory / f"{workspace_id}.db", self.settings.seed_path)
            workspace = Workspace(db, self.settings)
            if workspace.embeddings.status().pending:
                workspace.embeddings.sync()
            self.items[workspace_id] = workspace
        return self.items[workspace_id]


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

    def current_workspace(
        token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
    ) -> Workspace:
        workspace_id = verify(token, settings.cookie_secret)
        if not workspace_id:
            raise HTTPException(401, detail={"code": "unauthorized", "message": "Sign in required"})
        return workspaces.get(workspace_id)

    def limited(workspace: Workspace, category: str, maximum: int) -> None:
        with workspace.db.transaction() as conn:
            count = conn.execute(
                """SELECT COUNT(*) FROM quota_events WHERE category=?
                AND created_at >= datetime('now','-24 hours')""", (category,)
            ).fetchone()[0]
            if count >= maximum:
                raise HTTPException(429, detail={
                    "code": "quota_exceeded", "message": f"{category} daily limit reached"
                })
            conn.execute("INSERT INTO quota_events VALUES(?,?,datetime('now'))",
                         (f"quota_{uuid.uuid4().hex}", category))

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

    @app.get("/api/v1/status", response_model=StatusResponse)
    def status(workspace: Workspace = Depends(current_workspace)) -> StatusResponse:
        embedding = workspace.embeddings.status()
        with workspace.db.connect() as conn:
            pending = conn.execute(
                "SELECT COUNT(*) FROM proposals WHERE status='pending'"
            ).fetchone()[0]
        return StatusResponse(
            memories=workspace.db.count("memories"), sessions=workspace.db.count("sessions"),
            proposals_pending=pending, embeddings=embedding,
            aria_model=settings.aria_model, deep_model=settings.aria_deep_model,
            degraded=embedding.degraded or not bool(settings.openai_api_key),
        )

    @app.post("/api/v1/recall", response_model=RecallResponse)
    def recall(body: RecallRequest,
               workspace: Workspace = Depends(current_workspace)) -> RecallResponse:
        limited(workspace, "recall", settings.max_direct_recalls)
        return workspace.retriever.recall(body)

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
        projects = sorted({m.project for m in memories})
        nodes = [GraphNode(
            id=f"project:{p}", type="repository", label=p, project=p, status="active"
        ) for p in projects]
        nodes += [GraphNode(
            id=m.id, type=("decision" if m.kind == "decision" else m.entity_type),
            label=m.title, project=m.project, status=m.status, evidence_id=m.id,
        ) for m in memories]
        edges = [GraphEdge(
            id=f"edge:{m.id}", source=f"project:{m.project}", target=m.id, type="contains"
        ) for m in memories]
        return GraphResponse(nodes=nodes, edges=edges)

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

    @app.post("/api/v1/index/sync", response_model=SyncResponse)
    def sync(workspace: Workspace = Depends(current_workspace)) -> SyncResponse:
        if settings.cloud:
            raise HTTPException(403, "index sync is local/admin-only")
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
