export type Memory = {
  id: string;
  entity_type: "episode" | "fact";
  project: string;
  kind: string;
  status: string;
  title: string;
  content: string;
  reason: string;
  tags: string[];
  happened_at: string;
};

export type DeclaredDocument = {
  id: string;
  source_uri: string;
  repository: string;
  title: string;
  body: string;
  provides: string[];
  public_interfaces: string[];
  safe_edit_points: string[];
  risk_areas: string[];
  graph_rag_entities: string[];
  depends_on: string[];
  main_files: string[];
  kind: string;
  status: string;
  owner_area: string;
  audience: string;
  last_verified?: string;
};

export type RecallHit = {
  memory: Memory;
  score: number;
  lexical_score: number;
  dense_score: number;
  structural_score: number;
  provenance: string[];
};

export type Trace = {
  query_ms: number;
  candidates: number;
  embedding_provider: string;
  degraded: boolean;
  signals: string[];
};

export type Session = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  turn_count: number;
};

export type ProviderCredentialStatus = {
  provider: "openai";
  configured: boolean;
  expires_at?: string | null;
  persistence: "encrypted_browser_session";
};

export type Proposal = {
  id: string;
  session_id?: string | null;
  operation: string;
  payload: Record<string, unknown>;
  rationale: string;
  evidence_ids: string[];
  status: string;
  memory_id?: string;
  error?: string;
};

export type Audit = {
  id: string;
  action: string;
  actor: string;
  proposal_id?: string;
  memory_id?: string;
  detail: Record<string, unknown>;
  created_at: string;
};

export type GraphData = {
  nodes: {
    id: string; type: string; label: string; project: string; status: string;
    evidence_id?: string; stage: "declared" | "dense" | "durable" | "repository";
  }[];
  edges: {id: string; source: string; target: string; type: string}[];
};

export type ContextSource = {
  id: string;
  entity_type: "memory" | "document";
  title: string;
  repository: string;
  score: number;
  selection_reasons: string[];
  lexical_score: number;
  structural_score: number;
  dense_score: number;
  declared_score: number;
  dimension_contributions: Record<string, number>;
};

export type ContextPack = {
  repository_identity: {
    repository: string;
    source_uri?: string;
    kind?: string;
    status?: string;
    last_verified?: string;
  };
  declared_capabilities: string[];
  facts: Memory[];
  episodes: Memory[];
  documents: DeclaredDocument[];
  dependency_paths: string[][];
  safe_edit_points: string[];
  risk_areas: string[];
  sources: ContextSource[];
  token_estimate: number;
  token_budget: number;
  omitted_candidate_count: number;
  degraded: boolean;
  routing: Record<string, unknown>;
};

export type ArchitectureSource = {
  id: string;
  stable_id: string;
  entity_type: "architecture_document" | "architecture_section";
  source_uri: string;
  section_anchor?: string | null;
  evidence_class: "declared" | "derived" | "inferred";
  content_hash: string;
  score: number;
  selection_reasons: string[];
};

export type ArchitectureBrief = {
  schema_version: "command-center-architecture-brief-v1";
  mode: "boot" | "task";
  repository_identity: {
    id?: string;
    repository?: string;
    aliases?: string[];
    requested?: string;
    status?: string;
    source_revision?: string;
  };
  snapshot_receipt: {
    snapshot_id?: string;
    source_revision?: string;
    manifest_hash?: string;
    corpus_hash?: string;
    activated_at?: string;
  };
  health_summary: {
    coverage: number;
    valid_cards?: number;
    documents_scanned?: number;
    missing_card_count?: number;
    unresolved_edge_count?: number;
    ambiguous_edge_count?: number;
    embedding_coverage?: number;
    degraded: boolean;
  };
  subsystems: string[];
  documents: {
    id: string;
    stable_id: string;
    source_uri: string;
    title: string;
    kind: string;
    status: string;
    owner_area: string;
    provides: string[];
    public_interfaces: string[];
    depends_on: string[];
    safe_edit_points: string[];
    risk_areas: string[];
    content_hash: string;
  }[];
  sections: {
    id: string;
    document_version_id: string;
    source_uri: string;
    heading: string;
    body: string;
    content_hash: string;
  }[];
  interfaces: string[];
  dependency_paths: string[][];
  safe_edit_points: string[];
  risk_areas: string[];
  architecture_issues: {
    id: string;
    source_uri: string;
    code: string;
    severity: string;
  }[];
  sources: ArchitectureSource[];
  token_estimate: number;
  token_budget: number;
  omitted_candidate_count: number;
  degraded: boolean;
  degraded_reasons: string[];
  trace_id: string;
};

export type ArchitectureHealth = {
  repository_id?: string | null;
  repository_name?: string | null;
  snapshot_id?: string | null;
  snapshot_status?: string | null;
  source_revision?: string | null;
  coverage: number;
  documents_scanned: number;
  valid_cards: number;
  missing_cards: string[];
  stale_sources: {source_uri: string; reason: string}[];
  unresolved_edges: string[];
  ambiguous_edges: string[];
  embedding_coverage: number;
  degraded: boolean;
  degraded_reasons: string[];
};

export type Capability = {
  stable_id: string;
  version: number;
  name: string;
  kind: "workflow" | "skill" | "prompt_module" | "policy" | "tool_reference" | "template";
  description: string;
  triggers: string[];
  instructions: string;
  repositories: string[];
  required_tools: string[];
  trust_status: "verified" | "workspace" | "untrusted" | "retired";
  provenance: string;
  content_hash: string;
  verified_at: string;
  created_at: string;
  activation_count: number;
};

export type ScreenshotAnalysis = {
  image_hash: string;
  width: number;
  height: number;
  analyzed_width: number;
  analyzed_height: number;
  mime_type: string;
  findings: string[];
  findings_are_inferences: true;
  retained: false;
  model: string;
  degraded: boolean;
};

export type Handoff = {
  id: string;
  lineage_id: string;
  version: number;
  repository: string;
  original_request: string;
  screenshot?: ScreenshotAnalysis | null;
  capability_refs: string[];
  open_plan: string[];
  architecture: Partial<ArchitectureBrief> & Record<string, unknown>;
  evidence_sources: (ContextSource | ArchitectureSource)[];
  safe_edit_points: string[];
  risks: string[];
  tool_references: string[];
  token_estimate: number;
  omitted_candidates: number;
  degraded: boolean;
  status: "draft" | "published" | "revoked";
  creator: string;
  created_at: string;
  published_at?: string | null;
  revoked_at?: string | null;
  codex_command: string;
};
