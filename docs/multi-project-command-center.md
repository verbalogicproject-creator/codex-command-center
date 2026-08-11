# Multi-project Command Center contract

```yaml
ai_card:
  id: command-center.multi-project-control-plane
  repository: Command Center
  title: Multi-project Command Center Contract
  kind: domain_contract
  audience: [user, engineer, ai_agent]
  status: implemented
  owner_area: project portfolio and context composition
  main_files: [services/memory/aria_memory/context.py, services/memory/aria_memory/store.py, services/memory/aria_memory/toolbox.py, apps/web/app/page.tsx, apps/web/components/MemoryGraph.tsx]
  public_interfaces: ["GET /api/v1/projects", "POST /api/v1/context/pack", "POST /api/v1/handoffs", "PATCH /api/v1/sessions/{session_id}", "GET /api/v1/graph"]
  provides: [project inventory, project-scoped sessions, explicit cross-project context composition, bounded graph projections]
  depends_on: [command-center.architecture-awareness, command-center.handoffs, command-center.security-privacy]
  safe_edit_points: [additive application migrations, context composition policy, project inventory projection, bounded graph filters]
  risk_areas: [silent cross-project fallback, losing source ownership, treating an unregistered project as architecture-grounded, weakening release authentication]
  graph_rag_entities: [Project, Session, ContextManifest, Handoff, EvidenceReceipt]
  last_verified: 2026-08-11
```

Command Center is the control plane. Project Memory is the intended independent
data plane and is accessed through versioned APIs; Command Center must not read
its database directly. Until that service boundary is active, this repository
keeps a compatibility implementation with the same protected-write rules.

## Storage topology

The default is one database per authenticated workspace or tenant, with project
identity on every scoped record. A database per project is not the default
because it makes cross-project retrieval, temporal relationships, migrations,
and immutable context manifests needlessly federated. A sensitive project may
later select an isolated-store adapter and key while preserving the same API.

## Context composition

A context request names one target repository and zero or more source
repositories. Cross-project composition must set the explicit allow flag.
Selected evidence IDs are pinned ahead of ranked recall and cannot be silently
removed to meet a token budget. Every source retains its repository ownership.
Evidence outside the declared target/source set fails closed.

The persisted `command-center-context-composition-v1` manifest records target,
sources, explicit selections, whether the packet crosses repositories, and the
policy used. Published handoffs pin this manifest and return it during
activation. Source X can inform target Y without becoming a fact owned by Y.

## Sessions

Sessions record repository, goal, status, branch, revision, source repositories,
and optional parent continuation. New sessions default to Command Center scope.
Aria compiles context from that explicit scope rather than silently searching
every project. Session events and observations are not durable facts; model
output still requires a pending proposal and authenticated browser confirmation.

## Bounded graph delivery

The graph endpoint supports project, focus, depth, and node-limit projections.
Responses expose total and visible counts plus truncation. The web canvas adds a
project selector and defaults mobile layouts to one project, avoiding a full
portfolio Dagre layout on constrained devices. This remains an inspectable
projection, not a substitute for Project Memory's future temporal graph.

## Compatibility and degradation

Rich handoff and context prompts may contain 8,000 characters while direct
retrieval queries remain capped at 2,000. The compiler preserves the full
request and deterministically projects only the retrieval query, exposing the
projection and character counts in routing metadata.

An unregistered target repository remains visibly degraded. Command Center
does not invent architecture cards, aliases, revisions, or safe edit points for
another repository.
