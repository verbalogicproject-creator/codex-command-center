# Declared retrieval and context compiler

```yaml
ai_card:
  id: command-center.declared-context
  repository: Command Center
  title: Declared Retrieval and Context Compiler
  kind: architecture_contract
  audience: [engineer, ai_agent, evaluator]
  status: implemented
  owner_area: declared context
  main_files: [services/memory/aria_memory/context.py, services/memory/aria_memory/documents.py, services/memory/aria_memory/architecture]
  public_interfaces: ["POST /api/v1/context/pack", "POST /api/v1/architecture/brief", "command-center-task-pack-v2"]
  provides: [separate durable and declared evidence retrieval, bounded context compilation]
  depends_on: [command-center.architecture-awareness]
  safe_edit_points: [rank fusion weights, explicit packet budgets, provider-neutral declarations]
  risk_areas: [confusing legacy latest projection with immutable versions, loading whole corpora]
  graph_rag_entities: [ContextCompiler, ArchitectureCompiler, DeclaredDocumentStore]
  last_verified: 2026-07-18
```

## Mental model

Command Center follows one rule:

> Declare what is already known, use embeddings for ambiguity, and reserve the
> synthesis model for evidence-bound judgment.

The service keeps two entity classes deliberately separate:

| Entity | Describes | Examples |
|---|---|---|
| Document | How a system is shaped now | interfaces, dependencies, safe edits, risks |
| Memory | What happened or was decided | fact, episode, supersession, invalidation |

They are stored and embedded independently, then fused only for a query.
Architecture documents also have an immutable versioned representation used by
the shared ArchitectureBrief and published handoffs.

## Two declaration layers

The legacy latest projection accepts Command Center frontmatter with named
dimensions and powers `POST /api/v1/documents/recall`.

The canonical architecture layer accepts either root frontmatter or an
Atlas-style fenced YAML `ai_card`. Both normalize to the fleet-standard slots
and are selected by `.command-center/architecture.yaml`. It adds immutable
snapshots, AST H2 sections, typed explicit relationships, coverage health, and
historical evidence resolution. See
[full architecture awareness](architecture-awareness.md).

## Latest-projection AI-card frontmatter

The extended Command Center preset maps fields as follows:

| Role | Fields |
|---|---|
| Searchable text | `provides`, `public_interfaces`, `safe_edit_points`, `risk_areas` |
| Structural edges | `graph_rag_entities`, `depends_on`, `main_files` |
| Clusters | `kind`, `status`, `owner_area`, `audience` |
| Freshness | `last_verified` |

Every card also declares `id`, `repository`, `title`, and eight named dimensions.
See [the synthetic Command Center card](../fixtures/demo/documents/command-center.md).

Source URIs are calculated relative to the repository root. An absolute or
parent-traversing URI is rejected during ingestion.

## Named dimensions

The versioned `cc3-declared-v1` schema contains privacy, local-first, mobile
suitability, inspectability, implementation maturity, evidence strength,
operational risk, and decision relevance.

They are intentionally a small palette. A result returns every contribution, so
a user can distinguish “matched the words” from “declared as strong evidence for
this decision.”

## Four retrieval modes

`POST /api/v1/documents/recall` accepts:

- `lexical`: sanitized FTS5 BM25 only;
- `declared`: lexical + declared structural paths + dimensions;
- `dense`: persistent embedding cosine only;
- `hybrid`: all signals with intent-routed weighted reciprocal-rank fusion.

Dense retrieval is optional and failure-safe. Memory and document vectors live
in separate tables, keyed by independent canonical content hashes.

## Context and architecture packet APIs

The common interface for Aria, Codex hooks, and MCP is:

```http
POST /api/v1/context/pack
Content-Type: application/json

{
  "prompt": "Where is the safe place to change retrieval?",
  "repository": "Command Center",
  "token_budget": 2000,
  "memory_limit": 8,
  "document_limit": 8,
  "mode": "hybrid"
}
```

The response contains repository identity, declared capabilities, distinct
facts/episodes/documents, dependency paths, safe edit points, risks, source IDs
and selection reasons, signal contributions, the token bound and omitted count,
and degraded/model-routing metadata.

The compiler rank-fuses document and memory candidate lists, then walks the fused
order until the entity limits or token budget are reached. It never returns the
whole database merely because a model asked a broad question.

The estimate measures the serialized packet—including provenance metadata—not
only document bodies. This keeps the displayed bound honest.

`POST /api/v1/architecture/brief` compiles the versioned structure packet.
Remote MCP `build_task_pack` and `recall_context` return
`command-center-task-pack-v2`, keeping the ArchitectureBrief and durable
ContextPack as separate labelled members. Aria emits both SSE events. A handoff
copies the exact ArchitectureBrief at draft creation and publication freezes it.

## Provider-agnostic declarations

The AI-card convention is deliberately model-neutral. Files such as `.ngf.md`
remain ordinary Markdown with declared frontmatter and are matched by the
ingester’s `*.md` walk. The same packet can be consumed by Aria, Codex, Claude,
Gemini, or another agent without translating repository knowledge into a
provider-specific memory format.

## Provenance

The declaration layer is adapted from `frontmatter_rag` and its vendored
`declared_core`, pinned at commit
`a3b835b42126345e62edcd1308c8d84a299554d4`. Exact provenance is recorded in
[`VENDORED.json`](../services/memory/VENDORED.json), with license attribution in
[`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).

The integration intentionally does not use frontmatter RAG’s in-memory dense
cache. Command Center owns persistent embedding hashes for both entity classes.
