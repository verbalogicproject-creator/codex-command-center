---
id: doc_lifeos
repository: LifeOS
title: Authorized personal-context connector
provides:
  - Bounded personal context when an explicit authorized connector is used
public_interfaces:
  - authorized evidence connector
safe_edit_points:
  - connector boundary and source labels
risk_areas:
  - Never include personal notes in the public corpus
  - Never log prompt or personal memory bodies
graph_rag_entities:
  - consent
  - context freshness
  - Command Center
depends_on: []
main_files:
  - connectors/lifeos.py
kind: boundary-card
status: planned
owner_area: privacy
audience: coding-agents
last_verified: 2026-07-18
dimensions:
  privacy: 1.0
  local_first: 0.84
  mobile_suitability: 0.72
  inspectability: 0.9
  implementation_maturity: 0.34
  evidence_strength: 0.72
  operational_risk: 0.74
  decision_relevance: 0.82
---
# LifeOS

Only sanitized technical structure belongs in this corpus. Personal assessment
or validation material is explicitly excluded.
