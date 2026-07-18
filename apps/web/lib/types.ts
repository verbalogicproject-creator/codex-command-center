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

export type Proposal = {
  id: string;
  operation: string;
  payload: Record<string, unknown>;
  rationale: string;
  evidence_ids: string[];
  status: string;
  memory_id?: string;
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
  nodes: {id: string; type: string; label: string; project: string; status: string; evidence_id?: string}[];
  edges: {id: string; source: string; target: string; type: string}[];
};

