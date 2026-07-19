from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, SecretStr


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
    workspace_token: str | None = None
    token_id: str | None = None


class PairAuthRequest(BaseModel):
    code: str = Field(min_length=6, max_length=64)


class PairStartResponse(BaseModel):
    code: str
    expires_in_seconds: int


class ProviderCredentialSetRequest(BaseModel):
    api_key: SecretStr = Field(min_length=20, max_length=512)


class ProviderCredentialStatus(BaseModel):
    provider: Literal["openai"] = "openai"
    configured: bool
    expires_at: str | None = None
    persistence: Literal["encrypted_browser_session"] = "encrypted_browser_session"


CapabilityKind = Literal[
    "workflow", "skill", "prompt_module", "policy", "tool_reference", "template"
]
TrustStatus = Literal["verified", "workspace", "untrusted", "retired"]


class CapabilityInput(BaseModel):
    stable_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,79}$")
    name: str = Field(min_length=1, max_length=120)
    kind: CapabilityKind
    description: str = Field(min_length=1, max_length=1_000)
    triggers: list[str] = []
    instructions: str = Field(min_length=1, max_length=30_000)
    repositories: list[str] = []
    required_tools: list[str] = []
    trust_status: TrustStatus = "workspace"
    provenance: str = Field(min_length=1, max_length=2_000)


class Capability(CapabilityInput):
    version: int
    content_hash: str
    verified_at: str
    created_at: str
    activation_count: int = 0


class CapabilityList(BaseModel):
    items: list[Capability]


class CapabilityRecommendationRequest(BaseModel):
    request: str = Field(min_length=1, max_length=8_000)
    repository: str
    screenshot_findings: list[str] = []
    limit: int = Field(default=3, ge=1, le=10)


class CapabilityRecommendation(BaseModel):
    capability: Capability
    score: float
    selection_reasons: list[str]


class CapabilityRecommendations(BaseModel):
    items: list[CapabilityRecommendation]
    degraded: bool = False


class ScreenshotAnalyzeRequest(BaseModel):
    repository: str = Field(min_length=1, max_length=240)
    user_request: str = Field(min_length=1, max_length=8_000)
    image_base64: str = Field(min_length=8, max_length=14_000_000)
    mime_type: Literal["image/png", "image/jpeg", "image/webp"]
    retain: bool = False


class ScreenshotAnalysis(BaseModel):
    image_hash: str
    width: int
    height: int
    analyzed_width: int
    analyzed_height: int
    mime_type: str
    findings: list[str]
    findings_are_inferences: bool = True
    retained: bool = False
    model: str
    degraded: bool


VisualSourceRole = Literal["current", "reference", "constraint"]


class VisualSourceAnalyzeInput(BaseModel):
    role: VisualSourceRole
    label: str = Field(min_length=1, max_length=120)
    image_base64: str = Field(min_length=8, max_length=7_000_000)
    mime_type: Literal["image/png", "image/jpeg", "image/webp"]


class VisualSourceAnalysis(ScreenshotAnalysis):
    role: VisualSourceRole
    label: str


class VisualComparisonAnalyzeRequest(BaseModel):
    repository: str = Field(min_length=1, max_length=240)
    user_request: str = Field(min_length=1, max_length=8_000)
    target_surface: str = Field(min_length=1, max_length=160)
    sources: list[VisualSourceAnalyzeInput] = Field(min_length=2, max_length=4)


class VisualComparisonReceipt(BaseModel):
    schema_version: Literal["command-center-visual-comparison-v1"] = (
        "command-center-visual-comparison-v1"
    )
    target_surface: str
    sources: list[VisualSourceAnalysis]
    preserve: list[str]
    adopt: list[str]
    avoid: list[str]
    conflicts: list[str]
    unresolved: list[str]
    model: str
    degraded: bool
    degraded_reasons: list[str] = []
    retained: Literal[False] = False


HandoffStatus = Literal["draft", "published", "revoked"]


class PlanningReceipt(BaseModel):
    schema_version: Literal["command-center-planning-receipt-v1"] = (
        "command-center-planning-receipt-v1"
    )
    model: str
    capability_reference: dict[str, Any]
    architecture_snapshot: dict[str, Any]
    evidence_ids: list[str]
    generated_at: str
    degraded: bool
    degraded_reasons: list[str] = []


class RedesignSuggestionAction(BaseModel):
    id: Literal["prepare-in-handoff-builder"] = "prepare-in-handoff-builder"
    label: Literal["Prepare in Handoff Builder"] = "Prepare in Handoff Builder"
    surface: Literal["handoff"] = "handoff"


class RedesignSuggestion(BaseModel):
    schema_version: Literal["command-center-redesign-suggestion-v1"] = (
        "command-center-redesign-suggestion-v1"
    )
    repository_identity: dict[str, Any]
    primary_capability: dict[str, Any]
    alternatives: list[dict[str, Any]]
    selection_reasons: list[str]
    architecture_snapshot: dict[str, Any]
    evidence_ids: list[str]
    degraded: bool
    degraded_reasons: list[str] = []
    original_intent: str
    action: RedesignSuggestionAction = Field(default_factory=RedesignSuggestionAction)


class HandoffDraftRequest(BaseModel):
    repository: str = Field(min_length=1, max_length=240)
    original_request: str = Field(min_length=1, max_length=8_000)
    screenshot: ScreenshotAnalysis | None = None
    visual_brief: VisualComparisonReceipt | None = None
    capability_refs: list[str] = []
    open_plan: list[str] = []
    token_budget: int = Field(default=6_000, ge=512, le=8_000)


class HandoffUpdateRequest(BaseModel):
    original_request: str | None = Field(default=None, min_length=1, max_length=8_000)
    capability_refs: list[str] | None = None
    open_plan: list[str] | None = None


class Handoff(BaseModel):
    id: str
    lineage_id: str
    version: int
    repository: str
    original_request: str
    screenshot: ScreenshotAnalysis | None
    visual_brief: VisualComparisonReceipt | None
    capability_refs: list[str]
    open_plan: list[str]
    planning_receipt: PlanningReceipt
    architecture: dict[str, Any]
    evidence_sources: list[dict[str, Any]]
    safe_edit_points: list[str]
    risks: list[str]
    tool_references: list[str]
    token_estimate: int
    omitted_candidates: int
    degraded: bool
    status: HandoffStatus
    creator: str
    created_at: str
    published_at: str | None = None
    revoked_at: str | None = None
    codex_command: str


TourMode = Literal["overview", "redesign"]
TourSurface = Literal[
    "aria", "handoff", "capabilities", "recall", "graph", "timeline", "audit"
]


class TourScriptRequest(BaseModel):
    mode: TourMode = "overview"
    repository: str = Field(default="Command Center", min_length=1, max_length=240)
    handoff_id: str | None = Field(default=None, max_length=120)


class TourStep(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,79}$")
    surface: TourSurface
    target: str = Field(min_length=1, max_length=80)
    evidence_ids: list[str] = []
    narration: str = Field(min_length=1, max_length=700)
    action: str = Field(min_length=1, max_length=240)
    pause_reason: str | None = Field(default=None, max_length=240)


class TourScript(BaseModel):
    schema_version: Literal["command-center-tour-script-v1"] = (
        "command-center-tour-script-v1"
    )
    mode: TourMode
    model: str
    handoff_id: str | None = None
    steps: list[TourStep] = Field(min_length=1, max_length=12)
    generated_at: str
    degraded: bool
    degraded_reasons: list[str] = []


class HandoffList(BaseModel):
    items: list[Handoff]


class HandoffLoadRequest(BaseModel):
    handoff_id: str
    repository: str = Field(min_length=1, max_length=240)
    client_name: str = Field(default="Codex", max_length=120)
    session_id: str | None = Field(default=None, max_length=240)


class HandoffPacket(BaseModel):
    handoff_id: str
    repository_identity: dict[str, Any]
    workflow_instructions: list[dict[str, Any]]
    approved_open_plan: list[str]
    planning_receipt: PlanningReceipt
    screenshot_observations: list[dict[str, Any]]
    visual_comparison: VisualComparisonReceipt | None = None
    declared_architecture: dict[str, Any]
    memories_and_documents: list[dict[str, Any]]
    safe_edit_points: list[str]
    risks: list[str]
    available_tools: list[str]
    evidence_receipts: list[dict[str, Any]]
    token_estimate: int
    degraded: bool
    degraded_reasons: list[str]
    activation_id: str
    interview_required: bool = True


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


class DeclaredDimensions(BaseModel):
    schema_version: str = "cc3-declared-v1"
    privacy: float = 0.5
    local_first: float = 0.5
    mobile_suitability: float = 0.5
    inspectability: float = 0.5
    implementation_maturity: float = 0.5
    evidence_strength: float = 0.5
    operational_risk: float = 0.5
    decision_relevance: float = 0.5


class DocumentRecord(BaseModel):
    id: str
    source_uri: str
    repository: str
    title: str
    body: str
    provides: list[str] = []
    public_interfaces: list[str] = []
    safe_edit_points: list[str] = []
    risk_areas: list[str] = []
    graph_rag_entities: list[str] = []
    depends_on: list[str] = []
    main_files: list[str] = []
    kind: str = "ai-card"
    status: str = "active"
    owner_area: str = ""
    audience: str = ""
    last_verified: str | None = None
    dimensions: DeclaredDimensions = Field(default_factory=DeclaredDimensions)


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


RetrievalMode = Literal["lexical", "declared", "dense", "hybrid"]


class DocumentRecallRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    limit: int = Field(default=8, ge=1, le=25)
    repository: str | None = None
    mode: RetrievalMode = "hybrid"


class DocumentHit(BaseModel):
    document: DocumentRecord
    score: float
    lexical_score: float
    dense_score: float
    structural_score: float
    declared_score: float
    dimension_contributions: dict[str, float] = {}
    structural_paths: list[str] = []
    provenance: list[str] = []


class DocumentRecallResponse(BaseModel):
    hits: list[DocumentHit]
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
    service_version: str = "0.5.0"
    memories: int
    documents: int = 0
    sessions: int
    proposals_pending: int
    embeddings: EmbeddingStatus
    aria_model: str
    deep_model: str
    provider_credential_configured: bool = False
    degraded: bool


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    project: str
    status: str
    evidence_id: str | None = None
    stage: Literal["declared", "dense", "durable", "repository"] = "durable"


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


class Turn(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    evidence_ids: list[str]
    created_at: str


class TurnList(BaseModel):
    items: list[Turn]


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


class ProposalCreate(BaseModel):
    session_id: str | None = None
    operation: WriteOperation
    payload: dict[str, Any]
    rationale: str = Field(min_length=1, max_length=2_000)
    evidence_ids: list[str] = []


class ProposalList(BaseModel):
    items: list[Proposal]


class ContextPackRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8_000)
    repository: str | None = None
    token_budget: int = Field(default=2_000, ge=256, le=8_000)
    memory_limit: int = Field(default=8, ge=0, le=25)
    document_limit: int = Field(default=8, ge=0, le=25)
    mode: RetrievalMode = "hybrid"


class ContextSource(BaseModel):
    id: str
    entity_type: Literal["memory", "document"]
    title: str
    repository: str
    score: float
    selection_reasons: list[str]
    lexical_score: float = 0
    structural_score: float = 0
    dense_score: float = 0
    declared_score: float = 0
    dimension_contributions: dict[str, float] = {}


class ContextPack(BaseModel):
    repository_identity: dict[str, Any]
    declared_capabilities: list[str]
    facts: list[MemoryRecord]
    episodes: list[MemoryRecord]
    documents: list[DocumentRecord]
    dependency_paths: list[list[str]]
    safe_edit_points: list[str]
    risk_areas: list[str]
    sources: list[ContextSource]
    token_estimate: int
    token_budget: int
    omitted_candidate_count: int
    degraded: bool
    routing: dict[str, Any]


HookEventKind = Literal["session_start", "user_prompt_submit", "post_tool_use", "stop"]


class HookEventRequest(BaseModel):
    kind: HookEventKind
    repository: str = Field(min_length=1, max_length=240)
    session_id: str | None = Field(default=None, max_length=240)
    tool_name: str | None = Field(default=None, max_length=120)
    source_ids: list[str] = []
    detail: dict[str, Any] = {}


class HookEventResponse(BaseModel):
    id: str
    kind: HookEventKind
    accepted: bool = True
    proposal: Proposal | None = None


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
