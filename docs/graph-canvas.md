# Evidence graph canvas

```yaml
ai_card:
  id: command-center.graph-canvas
  repository: Command Center
  title: Evidence Graph Canvas
  kind: interface_contract
  audience: [user, engineer, ai_agent]
  status: implemented
  owner_area: visualization
  main_files: [apps/web/components/MemoryGraph.tsx, apps/web/components/ContextPulseEdge.tsx, apps/web/app/globals.css, docs/command-center-atlas.html, services/memory/aria_memory/app.py]
  public_interfaces: ["GET /api/v1/graph", "aria:graph-command"]
  provides: [typed evidence visualization, active handoff and Codex activation receipts]
  depends_on: [command-center.architecture-awareness, command-center.handoffs]
  safe_edit_points: [client-only layout and viewport state, typed semantic node rendering]
  risk_areas: [turning presentation state into a second graph store, hiding provenance]
  graph_rag_entities: [MemoryGraph, ArchitectureEdge, HandoffActivation]
  last_verified: 2026-07-18
```

The Knowledge Graph is a visual explanation of the evidence Command Center
already retrieved. It is not a second database, retrieval engine, or editable
workflow canvas.

## What users see

Each node answers three questions at a glance:

1. **What is it?** The icon and kind identify a repository, declared document,
   architecture section, capability, handoff, Codex client activation, fact,
   episode, or decision.
2. **Where did it come from?** The footer shows its repository or project.
3. **Why is it lit?** Cyan means the source is inside the context currently
   injected into Aria or Codex.

The semantic palette is fixed:

| Visual | Meaning |
|---|---|
| Violet card or edge | Declared repository, document, and stored capability structure |
| Amber card or edge | Human-authored or human-confirmed durable memory |
| Cyan card and moving particle | Sol-selected context or an audited active handoff entering Codex |
| Muted edge | A relationship that exists but is not active for this question |
| Dimmed card | Superseded evidence retained for provenance |

Selecting a node opens its source in the evidence drawer. The graph never
replaces the source record.

## Data flow

FastAPI returns typed semantic nodes and edges from `GET /api/v1/graph`. The
browser:

1. filters to the active evidence neighborhood on narrow screens;
2. calculates a left-to-right Dagre layout;
3. maps semantic stages to evidence-card tones;
4. maps active relationships to the context pulse edge;
5. opens the original evidence ID when a node is selected.

No graph position or decorative state is written to durable memory.

Callers can bound the projection with repeated `project` and `focus` query
parameters, `depth=0..2`, and `limit=25..500`. Responses distinguish total from
visible nodes and report truncation. The browser provides a project selector
and defaults narrow viewports to one project, preventing a full portfolio
Dagre pass from blocking the mobile canvas.

Published handoffs add cyan session-context nodes. Their incoming `injects`
edges originate at exact violet capability-version nodes.
`selected_for_handoff` edges connect exact evidence versions, and an audited
load adds `activated_in_codex` to the Codex node. A historical document pinned
by a handoff remains visible after a new snapshot activates. The handoff packet
and activation ID remain the source of truth; animation is only a visible
receipt.

## Components

- `MemoryGraph.tsx` adapts API graph data, performs layout, and renders evidence
  cards.
- `ContextPulseEdge.tsx` renders structural edge tones and the moving particle
  for active context.
- `InfiniteDock.tsx` provides the looping surface navigator used below every
  Command Center view.

These components are Command Center-native. They use the existing React Flow,
Dagre, Lucide, React, and plain-CSS stack; they do not import Canvas OS runtime
behavior, Tailwind, WebLLM, or editor state.

## Approved visual direction

The comparison handoff for the next graph iteration keeps evidence cards as the
primary node language. The interactive atlas is a role-labelled visual
reference, not a replacement specification. Candidate qualities to adopt are
its canvas atmosphere, type filters, connected-edge highlighting, and side
receipt inspector. The evidence-stage palette, stable evidence IDs, active
context meaning, repository data contract, narrow-screen neighborhood, and
reduced-motion behavior remain authoritative.

Taste and Codex must still interview around unresolved layout freedom,
temporary dragging, palette priority, and motion intensity. Publication of the
comparison handoff approves only the injected context; implementation begins
only after the user approves Codex's bounded plan.

## Mobile and accessibility

On screens up to 860 pixels wide, only active sources and their immediate
neighbors are shown. This keeps the map readable without changing the evidence
packet.

The dock repeats its visual sequence to create continuous horizontal wrapping,
but only its primary sequence participates in keyboard navigation and the
accessibility tree. Left and right arrow keys move between primary navigation
items. Vertical touch gestures remain available while horizontal dragging moves
the dock.

When `prefers-reduced-motion` is enabled, the traveling particle and glow are
hidden and state remains understandable through color, labels, icons, and
borders.

## Maintenance contract

- Do not encode retrieval scores only through color.
- Do not animate inactive relationships.
- Do not add an editable graph persistence path.
- Keep node clicks bound to stable evidence IDs.
- Keep semantic color mapping covered by frontend tests.
- Add new graph stages to the API type, node-tone mapper, legend, documentation,
  and tests in the same change.
