# Fenced Component

```yaml
ai_card:
  id: synthetic.fenced.component
  repository: Synthetic Architecture
  title: Fenced Component
  kind: architecture_doc
  audience:
    - engineer
    - ai_agent
  status: implemented
  owner_area: synthetic platform
  main_files:
    - services/synthetic/fenced.py
  public_interfaces:
    - "fenced_component.run()"
  provides:
    - fenced architecture fixture
  depends_on:
    - synthetic.shared.contract
  safe_edit_points:
    - fixture prose
  risk_areas:
    - fixture drift
  graph_rag_entities:
    - FencedComponent
  last_verified: 2026-07-18
```

## Purpose

Exercise the Atlas-style fenced `ai_card` architecture declaration.

## Contract

The fixture is synthetic and contains no private repository content.
