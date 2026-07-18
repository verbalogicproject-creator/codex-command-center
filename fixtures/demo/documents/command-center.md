---
id: doc_command_center
repository: Command Center
title: Command Center visual context compiler
provides:
  - Visual evidence graph and bounded context packets for coding agents
  - Human-gated durable memory proposals with an append-only audit trail
public_interfaces:
  - POST /api/v1/context/pack
  - POST /api/v1/recall
  - POST /api/v1/proposals/{id}/confirm
safe_edit_points:
  - services/memory/aria_memory/retrieval.py
  - services/memory/aria_memory/documents.py
  - apps/web/components/MemoryGraph.tsx
risk_areas:
  - Model-facing code must never confirm durable memory
  - Cloud workspaces are intentionally ephemeral
graph_rag_entities:
  - Project Memory
  - Aria
  - Codex
depends_on:
  - doc_project_memory
main_files:
  - services/memory/aria_memory/app.py
  - apps/web/app/page.tsx
kind: architecture
status: active
owner_area: agent-context
audience: coding-agents
last_verified: 2026-07-18
dimensions:
  privacy: 0.82
  local_first: 0.86
  mobile_suitability: 0.82
  inspectability: 1.0
  implementation_maturity: 0.88
  evidence_strength: 0.94
  operational_risk: 0.35
  decision_relevance: 1.0
---
# Command Center

Command Center compiles declared repository structure, relevant durable memory,
and retrieval provenance into a compact packet. The browser is the sole durable
write confirmation surface.
