from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ArchitectureDialect = Literal["frontmatter", "fenced-ai-card", "dual"]
EvidenceClass = Literal["declared", "derived", "inferred", "verified"]
IssueSeverity = Literal["info", "warning", "error"]
SnapshotStatus = Literal["staging", "active", "historical", "rejected"]


class ArchitectureIssue(BaseModel):
    code: str
    severity: IssueSeverity
    message: str
    source_uri: str
    field: str | None = None
    evidence_class: EvidenceClass = "derived"
    detail: dict[str, Any] = Field(default_factory=dict)


class ArchitectureCard(BaseModel):
    """Canonical provider-neutral form of both supported ai_card dialects."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str = "architecture_doc"
    audience: list[str] = Field(default_factory=list)
    status: str = "undocumented"
    owner_area: str = ""
    main_files: list[str] = Field(default_factory=list)
    public_interfaces: list[str] = Field(default_factory=list)
    provides: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    safe_edit_points: list[str] = Field(default_factory=list)
    risk_areas: list[str] = Field(default_factory=list)
    graph_rag_entities: list[str] = Field(default_factory=list)
    last_verified: str | None = None
    repository: str = ""
    title: str = ""
    dimensions: dict[str, float] = Field(default_factory=dict)
    relationships: list[dict[str, Any]] = Field(default_factory=list)


class ArchitectureSection(BaseModel):
    id: str
    document_id: str
    source_uri: str
    heading: str
    heading_slug: str
    ordinal: int
    body: str
    content_hash: str
    evidence_class: EvidenceClass = "derived"


class ArchitectureParseResult(BaseModel):
    source_uri: str
    content_hash: str
    dialect: ArchitectureDialect | None
    card: ArchitectureCard | None
    body: str
    sections: list[ArchitectureSection] = Field(default_factory=list)
    issues: list[ArchitectureIssue] = Field(default_factory=list)
    valid: bool = False


class ArchitectureSnapshot(BaseModel):
    id: str
    repository_id: str
    repository: str
    source_revision: str
    manifest_hash: str
    corpus_hash: str
    status: SnapshotStatus
    document_count: int
    valid_count: int
    issue_count: int
    created_at: str
    activated_at: str | None = None


class ArchitectureRepository(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    manifest_hash: str
    created_at: str
    updated_at: str


class ArchitectureDocumentVersion(BaseModel):
    id: str
    snapshot_id: str
    stable_id: str
    source_uri: str
    dialect: ArchitectureDialect
    title: str
    declaration: dict[str, Any]
    body: str
    content_hash: str
    last_verified: str | None = None
    created_at: str


class ArchitectureStoredSection(BaseModel):
    id: str
    document_version_id: str
    stable_id: str
    heading: str
    heading_slug: str
    ordinal: int
    body: str
    content_hash: str
    evidence_class: EvidenceClass


class ArchitectureEdge(BaseModel):
    id: str
    snapshot_id: str
    source_id: str
    target_ref: str
    target_id: str | None = None
    relation_type: str
    evidence_class: EvidenceClass
    resolution_status: Literal["resolved", "unresolved", "ambiguous"]
    source_document_version_id: str | None = None
    source_field: str
    created_at: str


class ArchitectureStoredIssue(BaseModel):
    id: str
    snapshot_id: str
    source_uri: str
    code: str
    severity: IssueSeverity
    detail: dict[str, Any] = Field(default_factory=dict)
    evidence_class: EvidenceClass
    created_at: str


class ArchitectureRepositoryIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,79}$")
    name: str = Field(min_length=1, max_length=240)
    aliases: list[str] = Field(default_factory=list, max_length=40)


class ArchitectureSyncDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_uri: str = Field(min_length=1, max_length=512)
    content: str = Field(max_length=524_288)


class ArchitectureSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: ArchitectureRepositoryIdentity
    source_revision: str = Field(default="", max_length=160)
    manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    documents: list[ArchitectureSyncDocument] = Field(
        min_length=1, max_length=1_000,
    )


class ArchitectureHashEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_uri: str = Field(min_length=1, max_length=512)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class ArchitectureCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str = Field(min_length=1, max_length=240)
    source_revision: str = Field(default="", max_length=160)
    manifest_hash: str | None = Field(
        default=None, pattern=r"^[a-f0-9]{64}$",
    )
    documents: list[ArchitectureHashEntry] = Field(
        default_factory=list, max_length=1_000,
    )


class ArchitectureHealth(BaseModel):
    repository_id: str | None = None
    repository: str
    aliases: list[str] = Field(default_factory=list)
    snapshot_id: str | None = None
    snapshot_status: SnapshotStatus | None = None
    source_revision: str = ""
    last_sync: str | None = None
    documents_scanned: int = 0
    valid_cards: int = 0
    coverage: float = 0
    missing_cards: list[str] = Field(default_factory=list)
    invalid_cards: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    stale_sources: list[dict[str, Any]] = Field(default_factory=list)
    unresolved_edges: list[dict[str, Any]] = Field(default_factory=list)
    ambiguous_edges: list[dict[str, Any]] = Field(default_factory=list)
    embedding_coverage: float = 0
    degraded: bool = False
    degraded_reasons: list[str] = Field(default_factory=list)


class ArchitectureSyncResponse(BaseModel):
    snapshot: ArchitectureSnapshot
    health: ArchitectureHealth


class ArchitectureLintRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: ArchitectureRepositoryIdentity
    documents: list[ArchitectureSyncDocument] = Field(
        min_length=1, max_length=1_000,
    )


class ArchitectureLintResponse(BaseModel):
    valid: bool
    document_count: int
    valid_cards: int
    coverage: float
    corpus_hash: str
    issues: list[ArchitectureIssue] = Field(default_factory=list)


class ArchitectureBriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str = Field(min_length=1, max_length=240)
    mode: Literal["boot", "task"] = "task"
    prompt: str = Field(default="", max_length=8_000)
    token_budget: int = Field(default=2_000, ge=256, le=8_000)
    document_limit: int = Field(default=8, ge=1, le=25)
    section_limit: int = Field(default=8, ge=0, le=25)


class ArchitectureBriefDocument(BaseModel):
    id: str
    stable_id: str
    source_uri: str
    title: str
    kind: str
    status: str
    owner_area: str
    audience: list[str] = Field(default_factory=list)
    provides: list[str] = Field(default_factory=list)
    public_interfaces: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    safe_edit_points: list[str] = Field(default_factory=list)
    risk_areas: list[str] = Field(default_factory=list)
    last_verified: str | None = None
    content_hash: str


class ArchitectureBriefSection(BaseModel):
    id: str
    document_version_id: str
    source_uri: str
    heading: str
    body: str
    content_hash: str


class ArchitectureSourceReceipt(BaseModel):
    id: str
    stable_id: str
    entity_type: Literal["architecture_document", "architecture_section"]
    source_uri: str
    section_anchor: str | None = None
    evidence_class: EvidenceClass
    content_hash: str
    score: float
    selection_reasons: list[str] = Field(default_factory=list)


class ArchitectureBrief(BaseModel):
    schema_version: str = "command-center-architecture-brief-v1"
    mode: Literal["boot", "task"]
    repository_identity: dict[str, Any]
    snapshot_receipt: dict[str, Any]
    health_summary: dict[str, Any]
    subsystems: list[str] = Field(default_factory=list)
    documents: list[ArchitectureBriefDocument] = Field(default_factory=list)
    sections: list[ArchitectureBriefSection] = Field(default_factory=list)
    interfaces: list[str] = Field(default_factory=list)
    dependency_paths: list[list[str]] = Field(default_factory=list)
    safe_edit_points: list[str] = Field(default_factory=list)
    risk_areas: list[str] = Field(default_factory=list)
    architecture_issues: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[ArchitectureSourceReceipt] = Field(default_factory=list)
    token_estimate: int
    token_budget: int
    omitted_candidate_count: int
    degraded: bool
    degraded_reasons: list[str] = Field(default_factory=list)
    trace_id: str
