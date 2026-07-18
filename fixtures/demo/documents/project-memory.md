---
id: doc_project_memory
repository: Project Memory
title: Durable evidence and hybrid recall
provides:
  - SQLite-backed facts and episodes with stable evidence IDs
  - Lexical structural and persistent dense retrieval
public_interfaces:
  - recall_context
  - get_evidence
  - get_timeline
safe_edit_points:
  - services/memory/aria_memory/store.py
  - services/memory/aria_memory/retrieval.py
risk_areas:
  - Episode and fact schema_version must remain one
  - Inactive facts must stay outside ordinary recall
graph_rag_entities:
  - Command Center
  - SQLite
  - evidence
depends_on: []
main_files:
  - services/memory/aria_memory/db.py
  - services/memory/aria_memory/embeddings.py
kind: subsystem
status: active
owner_area: durable-memory
audience: coding-agents
last_verified: 2026-07-18
dimensions:
  privacy: 0.92
  local_first: 1.0
  mobile_suitability: 0.76
  inspectability: 0.96
  implementation_maturity: 0.94
  evidence_strength: 0.95
  operational_risk: 0.28
  decision_relevance: 0.9
---
# Project Memory

Documents describe the system. Facts and episodes record what was observed,
decided, superseded, or invalidated. Those entity classes remain distinct.
