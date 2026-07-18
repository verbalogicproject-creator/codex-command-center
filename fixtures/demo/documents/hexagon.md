---
id: doc_hexagon
repository: Hexagon
title: On-device inference adapter
provides:
  - Future Qualcomm NPU inference provider for private mobile execution
public_interfaces:
  - inference provider adapter
safe_edit_points:
  - provider capability detection
risk_areas:
  - NPU integration is future work and must not be presented as shipped
  - Thermal driver and quantization variance require graceful fallback
graph_rag_entities:
  - Qualcomm NPU
  - mobile inference
  - Command Center
depends_on: []
main_files:
  - adapters/hexagon_provider.py
kind: capability-card
status: planned
owner_area: inference
audience: coding-agents
last_verified: 2026-07-18
dimensions:
  privacy: 1.0
  local_first: 1.0
  mobile_suitability: 1.0
  inspectability: 0.64
  implementation_maturity: 0.28
  evidence_strength: 0.58
  operational_risk: 0.82
  decision_relevance: 0.76
---
# Hexagon

Hexagon is an evidence source and provider boundary, not a repository to merge
into Command Center.
