from __future__ import annotations

import json
import logging
import time
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import Settings
from .mcp import handle_rpc
from .models import ErrorDetail, ErrorResponse
from .workspaces import Workspace, Workspaces

MCP_PROTOCOL_VERSION = "2025-06-18"


def create_mcp_app(settings: Settings | None = None) -> FastAPI:
    """Create the stateless remote-MCP boundary without general REST routes."""

    settings = settings or Settings()
    workspaces = Workspaces(settings)
    app = FastAPI(
        title="Codex Command Center MCP",
        version="0.5.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        responses={401: {"model": ErrorResponse}},
    )
    app.state.settings = settings
    app.state.workspaces = workspaces

    @app.middleware("http")
    async def structured_request_log(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        if settings.cloud:
            logging.getLogger("command_center.mcp.request").info(json.dumps({
                "event": "mcp_http_request",
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(
                    (time.perf_counter() - started) * 1000,
                    2,
                ),
            }, separators=(",", ":")))
        return response

    def current_workspace(
        command_token: Annotated[
            str | None,
            Header(alias="X-Command-Center-Token"),
        ] = None,
    ) -> Workspace:
        workspace_id = workspaces.resolve_workspace_token(command_token)
        if not workspace_id:
            raise HTTPException(401, detail={
                "code": "unauthorized",
                "message": "A paired Command Center workspace token is required.",
            })
        return workspaces.get(workspace_id)

    @app.get("/health")
    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "codex-command-center-mcp"}

    @app.post("/mcp")
    async def mcp_endpoint(
        request: Request,
        workspace: Workspace = Depends(current_workspace),
    ):
        try:
            message = await request.json()
        except ValueError:
            raise HTTPException(400, "invalid JSON-RPC body") from None
        if isinstance(message, list):
            result = [
                response
                for item in message
                if (response := handle_rpc(workspace, item)) is not None
            ]
        else:
            result = handle_rpc(workspace, message)
        if result is None:
            return Response(status_code=202)
        return JSONResponse(
            result,
            headers={"MCP-Protocol-Version": MCP_PROTOCOL_VERSION},
        )

    @app.get("/.well-known/oauth-authorization-server")
    @app.get("/.well-known/oauth-protected-resource")
    def oauth_metadata_not_configured():
        raise HTTPException(404, detail={
            "code": "oauth_metadata_unavailable",
            "message": "Use the Command Center one-time browser pairing flow.",
        })

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException):
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            detail = exc.detail
        else:
            detail = {
                "code": f"http_{exc.status_code}",
                "message": str(exc.detail),
            }
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(error=ErrorDetail(**detail)).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(error=ErrorDetail(
                code="validation_error",
                message="; ".join(error["msg"] for error in exc.errors()),
            )).model_dump(),
        )

    return app


app = create_mcp_app()
