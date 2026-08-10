# NLKE Grounded Continuity Architecture

```yaml
ai_card:
  id: command-center.nlke-gca
  repository: Command Center
  title: NLKE Grounded Continuity Architecture
  kind: architecture_specification
  audience: [users, engineers, evaluators, ai_agents]
  status: implemented
  owner_area: system architecture
  main_files: [services/memory/aria_memory, apps/web, plugins/codex-command-center]
  public_interfaces: [nlke-gca-grounding-receipt-v1, command-center-architecture-brief-v1, command-center-task-pack-v2]
  provides: [grounded continuity model, grounding compiler contract, immutable handoff protocol, human authority gates]
  depends_on: [command-center.architecture, command-center.architecture-awareness, command-center.architecture-exhibit]
  safe_edit_points: [additive receipt fields, new grounding adapters, implementation mappings]
  risk_areas: [confusing lineage with imported code, unbounded context, implicit authority, unsupported novelty claims]
  graph_rag_entities: [NLKE, NLKE-GCA, Grounding Compiler, Grounding Receipt, Immutable Handoff, Activation Receipt]
  last_verified: 2026-07-20
```

## Definition

**Natural Language Knowledge Engineering (NLKE)** is the broader methodology:
engineer explicit structures that humans and language models can inspect,
retrieve, challenge, and evolve together.

**NLKE Grounded Continuity Architecture (NLKE-GCA)** is Eyal Nof's named
architecture for carrying bounded, versioned understanding across people,
models, interfaces, sessions, and implementation tools without treating hidden
model state as memory or capability as permission.

**Codex Command Center is its first public reference implementation.** Aria is
the operating agent, the Grounding Compiler is the selection boundary, and
Codex is the implementation client in the Build Week reference workflow.

This is an implemented architecture claim, not a claim that every supporting
research project is bundled into this repository. The private NLKE, Atlas,
Declarum, `kg-factory`, and ARIA systems are research and implementation
lineage. Command Center reimplements selected patterns under its own contracts.

## Problem

An agent can produce a plausible answer while still losing the repository's
architecture, the human's prior decisions, the visual target, or the exact
capability that should govern execution. Loading more chat history does not
solve this reliably: history is unbounded, authority is ambiguous, and neither
selection nor omission is inspectable.

NLKE-GCA replaces assumed continuity with a compiled contract:

```text
declared sources
  → repository and workspace scope
  → deterministic selection and bounding
  → visible grounding receipt
  → immutable handoff
  → verified client activation
```

## Four grounding layers

1. **Durable collaboration** — human-confirmed decisions, episodes, facts,
   sessions, typed/spoken turns, pending proposals, and audit receipts.
2. **Declared repository architecture** — versioned architecture cards,
   sections, explicit edges, gaps, source hashes, and immutable snapshots.
3. **Human and visual intent** — role-labelled visual findings, preserve/adopt/
   avoid decisions, unresolved questions, and a reversible Open Plan.
4. **Executable context** — trusted capability versions, scoped semantic
   commands, current workflow state, and bounded delivery profiles.

A grounding source is one inspectable record within a layer. Grounding is the
larger promise that only the relevant, scoped sources cross into an agent
context. Existing `evidence_id` API fields remain compatible technical names
for individual source identifiers.

## Grounding Compiler

The Grounding Compiler is a deterministic policy boundary rather than a
general-purpose summarizer. Its reference lifecycle is:

1. Resolve an exact workspace and repository identity; unknown identity fails
   closed.
2. Load a small global set and add sources for the current surface, workflow,
   visible draft, tour, or drawer.
3. Rank across declared architecture, durable collaboration, intent, and
   capability sources without merging their authority classes.
4. Enforce serialized packet and token bounds.
5. Remove orphaned dependency paths after eviction.
6. Record selected sources, versions, omissions, hashes, and degraded reasons.
7. Freeze the result when the human publishes a handoff.
8. Verify repository identity again when a client loads it and record a
   separate activation receipt.

Optional dense or model-backed stages may degrade. Repository identity,
confirmation, trust, immutability, and privacy rules may not.

## Grounding receipt

The public architecture exhibit uses
`nlke-gca-grounding-receipt-v1`:

```json
{
  "schema_version": "nlke-gca-grounding-receipt-v1",
  "claim_id": "immutable-handoff",
  "claim": "Published handoffs cannot silently change",
  "implementation_status": "implemented",
  "source_revision": "public Git ref",
  "snapshot_hash": "sha256",
  "grounding_path": [
    {"kind": "interface", "source": "visible product control"},
    {"kind": "route", "source": "authenticated API boundary"},
    {"kind": "symbol", "source": "allow-listed Python behavior"},
    {"kind": "table", "source": "SQLite/PostgreSQL contract"},
    {"kind": "test", "source": "regression proof"}
  ],
  "failure_behavior": "A direct mutation returns a conflict."
}
```

The exhibit is a static projection. It contains source locations and bounded
excerpts, never live workspace rows, credentials, prompts, audio, screenshots,
or private repository content.

## Human authority invariants

- Models may propose durable memory; only an authenticated human tap confirms
  it.
- Handoff publication requires the exact phrase **Approve this handoff.**
- Voice cannot upload files, edit code, install, deploy, confirm memory, expose
  secrets, invent capability references, or bypass repository trust.
- Database command records select metadata, scope, and aliases; executable
  behavior remains in an allow-listed controller.
- Published handoffs are immutable. Editing creates a new lineage version.
- Loading a handoff never implies permission to edit; it creates an activation
  receipt and begins the declared interview or implementation workflow.
- Raw audio, WebRTC payloads, provider credentials, and screenshot pixels are
  not durable grounding sources.

## Continuity without hidden memory

NLKE-GCA does not claim perfect memory. It makes continuity falsifiable:

- the selected context is visible;
- omitted candidates are counted;
- degraded stages are named;
- durable writes have an authority trail;
- source versions remain inspectable;
- a client proves which packet it activated.

The result is continuity without hidden memory and grounding without
surrendered control.

## Research lineage

The timestamped June 2025
[Manual Memory Log](https://community.openai.com/t/how-i-simulated-memory-in-free-chatgpt-using-logic-alone-manual-memory-log-method/1286932)
records the originating principle thirteen months before this Build Week
implementation, before the author knew the vocabulary of RAG
or agent frameworks: explicit context, factual framing, one inspectable source
of truth, and logic-gated progression.

| June 2025 manual principle | NLKE-GCA implementation |
|---|---|
| Maintain one structured Memory Log | Durable collaboration sources with explicit authority classes |
| Context is supplied, never assumed | Context-on-demand through the Grounding Compiler |
| Only explicit facts influence reasoning | Versioned source IDs, selection reasons, and grounding receipts |
| New conclusions follow known inputs | Repository scope, human gates, immutable handoffs, and fail-closed behavior |

Subsequent projects tested different parts of the method:

- the Python NLKE framework tested structure-aware extraction, hybrid
  retrieval, temporal facts, code knowledge graphs, and memory-to-code
  provenance;
- Atlas and `kg-factory` tested inspectable architecture graphs and progressive
  visual projection;
- Declarum tested declaration-driven growth, lint, scaffold, staleness, and
  minimal boot context;
- ARIA tested context-on-demand, scoped semantic commands, serialized UI state,
  and runtime diagnostics;
- the public Claude Toolbox Curriculum tested portable MCP, extensibility,
  testing, and Cloud Run delivery patterns;
- Command Center composes the relevant patterns into one OpenAI/Codex-centered
  product and verifies them through source-backed receipts.

These are lineage statements, not endorsements or claims that private source
code is present here.
