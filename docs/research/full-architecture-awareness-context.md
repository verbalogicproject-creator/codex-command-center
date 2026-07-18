---
id: command-center.full-architecture-awareness.research
repository: Command Center
title: Full Architecture Awareness Research Context
kind: research
audience:
  - engineer
  - ai_agent
  - evaluator
status: verified
owner_area: declared context
main_files:
  - services/memory/aria_memory/documents.py
  - services/memory/aria_memory/context.py
  - services/memory/frontmatter_rag/presets.py
  - plugins/codex-command-center
public_interfaces:
  - "ArchitectureCard ingestion"
  - "ArchitectureBrief compilation"
  - "Codex SessionStart and UserPromptSubmit context"
provides:
  - durable research handoff for the architecture-awareness implementation
  - evidence-backed adoption map from Atlas and NLKE Declarum
  - definition of full architecture awareness
depends_on:
  - command-center.declared-context
  - command-center.codex-plugin
safe_edit_points:
  - canonical ArchitectureCard normalization
  - section-level document indexing
  - architecture health and coverage reporting
risk_areas:
  - loading whole repositories into prompts
  - presenting inferred relationships as declared facts
  - copying reference limitations into Command Center
graph_rag_entities:
  - ArchitectureCard
  - ArchitectureSection
  - ArchitectureBrief
  - ArchitectureHealth
  - Codex Command Center
last_verified: 2026-07-18
dimensions:
  inspectability: 1.0
  implementation_maturity: 0.8
  evidence_strength: 1.0
  decision_relevance: 1.0
---

# Full Architecture Awareness Research Context

## Objective

Give Aria and Codex the same bounded, evidence-bound understanding of the
active repository before planning or editing. The system must know the
repository's declared subsystems, interfaces, dependency paths, safe edit
points, risks, implementation status, freshness, and documentation gaps.

Full architecture awareness does not mean injecting every document or source
file into every prompt. It means that the complete declared architecture is
indexed and queryable, while each model receives only the smallest relevant
brief with source receipts.

## Project provenance

This work consolidates architectures already built and exercised by the project
author. It is not a speculative architecture-awareness prototype.

- Atlas / `kg-factory` proves architecture-document cards, deterministic
  Markdown section chunking, PostgreSQL graph nodes, degraded gap nodes, and
  idempotent ingestion.
- NLKE Declarum Game Engine proves the fleet-standard 13-slot declaration,
  minimal session boot index, document lint and scaffolding, staleness checks,
  hybrid retrieval, MCP exposure, and evidence-shaped question responses.
- Command Center already proves rich structured document persistence,
  lexical/structural/dense retrieval, bounded context compilation, evidence
  receipts, immutable handoffs, SQLite/PostgreSQL parity, and Codex hooks.

The author's self-taught context and knowledge engineering work is the direct
line connecting these systems. The accurate submission narrative is that
Command Center productizes a body of working architecture patterns into a
portable Aria-to-Codex workflow.

## Reference evidence

### Atlas / kg-factory

Implementation evidence:

- `backend/arch_doc_ingestion.py`
- `backend/tests/test_arch_doc_ingestion.py`
- `docs/architecture/README.md`
- `docs/architecture/shared/graph-rag-readiness.md`
- `docs/architecture/agent-md-format.schema.json`

Verified behavior:

- Finds the first fenced YAML block whose top-level key is `ai_card`.
- Normalizes scalar audiences to lists without mutating the parsed input.
- Uses a Markdown AST to split H2 sections without false splits inside fences.
- Creates one `architecture_doc` node and one `architecture_section` node per
  H2 section in the PostgreSQL `architecture` graph.
- Uses stable declared IDs with deterministic degraded IDs for missing cards.
- Re-ingestion is idempotent.
- The documented relationship taxonomy includes `DESCRIBES`, `DEPENDS_ON`,
  `PROVIDES`, `CALLS`, `OWNS_CONTRACT`, `PERSISTS_TO`, `SAFE_EDIT_POINT`, and
  `RISK_AREA`.

Verified limitation:

- The current ingester creates document and section nodes but does not
  materialize the documented relationship taxonomy as graph edges.

### NLKE Declarum Game Engine

Implementation evidence:

- `CLAUDE.md`
- `project-graph-memory/CLAUDE.md`
- `project-graph-memory/py/doc/ingest_tree.py`
- `project-graph-memory/py/doc/staleness.py`
- `project-graph-memory/py/mcp/tools/doc.py`
- `project-graph-memory/py/asks/base.py`
- `project-graph-memory/py/tests/test_doc_ingest.py`
- `docs/architecture/memory/README.md`
- `docs/architecture/memory/asks.md`

Verified behavior:

- Uses a strict 13-slot card:
  `id`, `kind`, `audience`, `status`, `owner_area`, `main_files`,
  `public_interfaces`, `provides`, `depends_on`, `safe_edit_points`,
  `risk_areas`, `graph_rag_entities`, and `last_verified`.
- Treats declaration as stronger evidence than inference.
- Keeps the automatically loaded session guide minimal and follows pointers
  lazily.
- Ingests document pointers idempotently and supports a no-write dry run.
- Provides MCP tools for ingest, search, lint, scaffold, and staleness.
- Keeps BM25 available when the optional dense booster is unavailable.
- Returns a common answer contract with answer, confidence, evidence, caveats,
  suggested next actions, and a trace ID.

Verified limitations:

- The compact `doc_pointers` table flattens several card fields into purpose and
  tags instead of preserving the full declared structure.
- Staleness is based on filesystem modification time, which is insufficient as
  the only freshness signal after a checkout or file copy.

### Command Center

Current implementation evidence:

- `services/memory/aria_memory/documents.py`
- `services/memory/aria_memory/context.py`
- `services/memory/frontmatter_rag/presets.py`
- `services/memory/aria_memory/toolbox.py`
- `services/memory/aria_memory/mcp.py`
- `plugins/codex-command-center`
- `docs/declared-context.md`
- `docs/codex-plugin.md`

Already implemented:

- Preserves the 13 declared fields as structured data rather than flattening
  them into a generic pointer.
- Stores repository-relative source URIs and rejects traversal.
- Supports lexical, declared, dense, and hybrid document recall.
- Compiles bounded packets with evidence IDs, selection reasons, safe edit
  points, risks, dependency paths, omissions, and degraded metadata.
- Shares tool schemas between the HTTP MCP and stdio adapter.
- Gives Codex `SessionStart`, `UserPromptSubmit`, sanitized `PostToolUse`, and
  `Stop` hooks.
- Loads immutable, repository-verified handoffs with activation receipts.

Missing for full architecture awareness:

- A canonical parser accepting both fenced `ai_card` blocks and YAML
  frontmatter.
- Strict schema validation, scaffolding, coverage, and freshness reporting.
- AST-derived section records and section-level retrieval.
- Materialized typed relationships between documents, sections, files,
  interfaces, capabilities, risks, and safe edit points.
- A compact repository boot manifest separate from task-specific retrieval.
- A first-class `ArchitectureBrief` result shared by Aria, handoffs, MCP, and
  Codex hooks.
- Architecture-specific acceptance and end-to-end tests.

## Canonical synthesis

### One normalized card

Both source dialects normalize into the existing Command Center record:

1. YAML frontmatter with the 13 slots at the root.
2. A fenced YAML block containing an `ai_card` object.

Parsing records the dialect and source provenance. Conflicting dual
declarations fail lint rather than silently choosing one.

### Four context tiers

1. **Boot manifest:** repository identity, architecture entrypoints, health,
   coverage, and the most important subsystem pointers.
2. **Architecture cards:** compact declared contracts selected for the task.
3. **Architecture sections:** relevant H2 chunks with stable section IDs.
4. **Source evidence:** exact files, interfaces, tests, and history opened only
   when required for verification.

### Evidence classes

- **Declared:** values copied from a validated card.
- **Derived:** deterministic structure such as an H2 section or normalized
  repository-relative path.
- **Inferred:** model-generated connections or screenshot observations.
- **Verified:** a declaration or inference checked against source evidence at a
  recorded revision or content hash.

The packet and interface must preserve these labels.

### Shared ArchitectureBrief

Aria planning, handoff publication, remote MCP, the stdio adapter, and Codex
hooks consume the same compiler output. A brief contains:

- repository identity and source revision;
- relevant subsystem cards and section excerpts;
- public interfaces and dependency paths;
- safe edit points and risks;
- evidence IDs and selection reasons;
- freshness, coverage, omissions, conflicts, and degraded state;
- token estimate and budget;
- a trace ID suitable for an activation receipt.

## Codex plugin consequence

The plugin upgrade is part of architecture awareness, not a separate cosmetic
task.

- `SessionStart` loads the boot manifest and architecture health.
- `UserPromptSubmit` loads the task-specific ArchitectureBrief.
- `load_handoff` loads the immutable brief and pinned capability versions.
- Codex reports injected evidence, gaps, freshness, and degraded state before
  asking its first interview question.
- Installed development copies use the Codex cachebuster and reinstall flow
  after the repository plugin validates. Marketplace files are not edited by
  hand during an update.

## PostgreSQL and proot

Atlas provides a proven PostgreSQL/pgvector route through Ubuntu under
`proot-distro`. Use it to validate the PostgreSQL behavioral contract and
container-like deployment behavior from the current device. Cloud SQL remains
the production persistence boundary. If local deployment tooling is incomplete,
the public repository can be pulled on the laptop for a clean Codex install,
plugin installation, Cloud Build, and Cloud Run deployment demonstration.

## Non-negotiable boundaries

- Architecture documents contain declarations and references, not arbitrary
  executable code.
- Missing optional dense retrieval produces explicit degraded metadata.
- Repository mismatch remains a hard failure for handoff activation.
- Voice may publish bounded context but may not edit code, install tools,
  approve durable memory, or perform deployment actions.
- Tokens never enter repository files, handoffs, URLs, or logs.
- Provider-specific boot files may point to Command Center, but the stored
  architecture and compiled brief remain provider-neutral.
- Documentation must distinguish implemented behavior, verified adoption work,
  and roadmap items.

## Planning baseline

The implementation plan should treat the remaining work as integration and
hardening:

1. normalize and validate the two proven card dialects;
2. add section records, typed graph edges, coverage, and freshness;
3. compile one shared ArchitectureBrief;
4. integrate it with Aria, handoffs, MCP, and the Codex plugin;
5. validate SQLite, PostgreSQL/proot, browser, plugin, and end-to-end behavior;
6. update the complete documentation and competition provenance narrative.
