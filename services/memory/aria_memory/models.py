from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool = False


class ErrorResponse(BaseModel):
    error: ErrorDetail


class DemoAuthRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)


class AuthResponse(BaseModel):
    authenticated: bool
    workspace_id: str


class MemoryRecord(BaseModel):
    id: str
    entity_type: Literal["episode", "fact"]
    project: str
    kind: str
    status: str
    title: str
    content: str
    reason: str = ""
    tags: list[str] = []
    happened_at: str
    created_at: str
    supersedes_id: str | None = None


class RecallRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    limit: int = Field(default=8, ge=1, le=25)
    project: str | None = None
    kinds: list[str] = []


class RecallHit(BaseModel):
    memory: MemoryRecord
    score: float
    lexical_score: float
    dense_score: float
    structural_score: float
    provenance: list[str]


class RetrievalTrace(BaseModel):
    query_ms: float
    candidates: int
    embedding_provider: str
    query_embedding_calls: int
    degraded: bool
    signals: list[str]


class RecallResponse(BaseModel):
    hits: list[RecallHit]
    trace: RetrievalTrace


class EmbeddingStatus(BaseModel):
    provider: str
    model: str
    dimensions: int
    indexed: int
    eligible: int
    pending: int
    coverage: float
    degraded: bool


class StatusResponse(BaseModel):
    memories: int
    sessions: int
    proposals_pending: int
    embeddings: EmbeddingStatus
    aria_model: str
    deep_model: str
    degraded: bool


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    project: str
    status: str
    evidence_id: str | None = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class TimelineResponse(BaseModel):
    items: list[MemoryRecord]


class SessionCreate(BaseModel):
    title: str = Field(default="New synthesis", min_length=1, max_length=120)


class Session(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    turn_count: int = 0


class SessionList(BaseModel):
    items: list[Session]


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=8_000)
    deep_synthesis: bool = False


WriteOperation = Literal[
    "remember_episode", "record_fact", "supersede_fact", "invalidate_fact"
]


class Proposal(BaseModel):
    id: str
    session_id: str | None
    operation: WriteOperation
    payload: dict[str, Any]
    rationale: str
    evidence_ids: list[str]
    status: Literal["pending", "confirmed", "rejected", "failed"]
    created_at: str
    resolved_at: str | None = None
    memory_id: str | None = None
    error: str | None = None


class AuditEvent(BaseModel):
    id: str
    action: str
    actor: str
    proposal_id: str | None
    memory_id: str | None
    detail: dict[str, Any]
    created_at: str


class AuditResponse(BaseModel):
    items: list[AuditEvent]


class SyncResponse(BaseModel):
    indexed: int
    deleted: int
    unchanged: int
    failed: int
    status: EmbeddingStatus


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
