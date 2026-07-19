# Capability authoring manual

```yaml
ai_card:
  id: command-center.capability-authoring
  repository: Command Center
  title: Capability Authoring Manual
  kind: authoring_guide
  audience: [user, engineer, ai_agent]
  status: implemented
  owner_area: capability library
  main_files: [services/memory/aria_memory/toolbox.py, services/memory/aria_memory/models.py]
  public_interfaces: ["/api/v1/capabilities", "search_capabilities", "get_capability"]
  provides: [provider-neutral capability schema, versioning and trust guidance]
  depends_on: [command-center.api-mcp, command-center.security-privacy]
  safe_edit_points: [new immutable capability versions, workspace-trusted instructions]
  risk_areas: [embedding executable code, weakening trust filtering]
  graph_rag_entities: [Capability, CapabilityLibrary]
  last_verified: 2026-07-19
```

Capabilities are versioned, provider-neutral instructions. They are not
executable packages and are never dynamically installed into a coding client.
Only the exact selected capability version enters a task handoff.

## Kinds

| Kind | Use |
|---|---|
| `workflow` | Ordered interview and implementation behavior |
| `skill` | Specialized domain instructions |
| `prompt_module` | Reusable model-facing framing |
| `policy` | Approval, safety, or quality boundary |
| `tool_reference` | Describes a tool and when it is available |
| `template` | Reusable plan or review structure |

## Required fields

```json
{
  "stable_id": "design-system-migration",
  "name": "Design system migration",
  "kind": "workflow",
  "description": "Plan a bounded component migration.",
  "triggers": ["design system", "tokens", "component migration"],
  "instructions": "Inspect cited components. Interview before editing...",
  "repositories": ["Command Center"],
  "required_tools": ["get_evidence", "walk_dependencies"],
  "trust_status": "workspace",
  "provenance": "Authored and reviewed by the frontend team."
}
```

`stable_id` is lower-case and stable across versions. Creating another record
with the same ID creates the next integer version. The server computes a
canonical SHA-256 content hash and records creation and verification times.

Use `*` in `repositories` for a portable capability. Use a concrete repository
name when the instructions depend on declared project structure. Required tools
are references, not installation requests.

## Trust

- `verified`: built-in or administrator-reviewed import. Ordinary API authoring
  requests are downgraded to `workspace`.
- `workspace`: authored within the current trusted workspace.
- `untrusted`: stored but omitted from normal search, recommendation, and
  handoff construction.
- `retired`: preserved for old handoffs but not selected for new ones.

Published handoffs pin `stable_id@version`, so later authoring never changes an
existing packet. Provenance should state who or what produced the instructions,
the evidence used, and the review boundary.

## Good instructions

A capability should tell the client:

1. when to stop and interview;
2. which evidence to inspect;
3. how to distinguish facts from inferences;
4. safe edit and approval boundaries;
5. required verification;
6. what it must not claim or perform.

Avoid provider names, hidden prompts, secrets, shell payloads, arbitrary code,
tool-installation directions, and instructions that bypass client approvals.

## API workflow

```sh
curl -X POST "$COMMAND_CENTER_URL/api/v1/capabilities" \
  -H "Content-Type: application/json" \
  -H "X-Command-Center-Token: $COMMAND_CENTER_TOKEN" \
  --data @capability.json
```

Search through REST `GET /api/v1/capabilities` or MCP
`search_capabilities`. Recommend with REST
`POST /api/v1/capabilities/recommend` or MCP
`recommend_capabilities`. Load an exact version with `get_capability`.

The six built-ins are Taste-guided frontend redesign interview, lightweight
frontend redesign interview, mobile accessibility review, graph-canvas
integration, evidence-bound coding plan, and safe deployment preparation.

## Taste-guided redesign

`taste-frontend-redesign-interview` is the primary workflow for an existing
frontend plus screenshot. It is a bounded, reviewed adaptation of Taste Skill
v2 experimental and `redesign-existing-projects`, not a dynamic installation of
the upstream skill collection.

The workflow makes Codex:

1. show the exact repository, snapshot, capability version, content hash, and
   evidence receipts;
2. distinguish screenshot inferences from declared repository facts;
3. classify targeted evolution, structural redesign, or greenfield work;
4. propose and interview around `DESIGN_VARIANCE`, `MOTION_INTENSITY`, and
   `VISUAL_DENSITY`;
5. audit existing typography, palette, layout, responsive behavior,
   accessibility, states, content, performance, and preservation boundaries;
6. produce an editable design contract and evidence-cited implementation plan;
7. ask the next focused question instead of editing immediately.

The capability deliberately does not impose marketing-page patterns on dense
application surfaces. Declared architecture and the existing design system take
precedence. Routes, navigation labels, form contracts, analytics identifiers,
legal copy, brand marks, and durable data semantics never change silently.

The retained upstream MIT terms are in
[`services/memory/TASTE_SKILL_LICENSE`](../services/memory/TASTE_SKILL_LICENSE).
The capability provenance records the upstream project, author, review date,
and SHA-256 hashes of both adapted instruction sources.

Built-in seeding is content-addressed. Starting a workspace checks every
reviewed built-in independently and inserts a new immutable version only when
that exact `(stable_id, content_hash)` is absent. Existing workspaces therefore
receive new built-ins without duplicating them on every restart.

Verify the selection and injection chain:

```sh
PYTHONPATH=services/memory pytest -q \
  services/memory/tests/test_toolbox.py
```

The contract test proves recommendation, exact-version handoff pinning, MCP
`get_capability`, and idempotent seeding into an already populated workspace.
