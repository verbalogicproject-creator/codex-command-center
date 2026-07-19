---
id: command-center.architecture-awareness
repository: Command Center
title: Full Architecture Awareness
kind: architecture_contract
audience:
  - user
  - engineer
  - ai_agent
  - evaluator
status: implemented
owner_area: declared context
main_files:
  - .command-center/architecture.yaml
  - services/memory/aria_memory/architecture
  - services/memory/aria_memory/toolbox.py
  - services/memory/aria_memory/mcp.py
  - services/memory/aria_memory/agent.py
  - plugins/codex-command-center
public_interfaces:
  - "POST /api/v1/architecture/lint"
  - "POST /api/v1/architecture/sync"
  - "POST /api/v1/architecture/check"
  - "GET /api/v1/architecture/health"
  - "POST /api/v1/architecture/brief"
  - "command-center-architecture-brief-v1"
  - "command-center-task-pack-v2"
provides:
  - shared versioned repository understanding for Aria and Codex
  - bounded boot and task architecture briefs
  - immutable source receipts and visible degraded metadata
depends_on:
  - command-center.architecture
  - command-center.declared-context
  - command-center.handoffs
  - command-center.codex-plugin
safe_edit_points:
  - architecture card declarations in selected Markdown
  - explicit repository aliases in the architecture manifest
  - compiler ranking and token budgets with receipt-preserving tests
risk_areas:
  - implicit document upload from session hooks
  - cross-repository fallback
  - mutable evidence inside published handoffs
  - presenting inferred relationships as declared
graph_rag_entities:
  - ArchitectureCard
  - ArchitectureSnapshot
  - ArchitectureDocumentVersion
  - ArchitectureSection
  - ArchitectureEdge
  - ArchitectureIssue
  - ArchitectureBrief
last_verified: 2026-07-18
---

# Full architecture awareness

Full architecture awareness means the complete declared architecture is
versioned and queryable while each model receives only the relevant,
repository-scoped portion. It does not mean loading the whole repository or
documentation corpus into every prompt.

Aria, published handoffs, the remote MCP, the stdio adapter, and Codex hooks all
consume the same `command-center-architecture-brief-v1` structure. A brief
contains:

- exact repository identity and accepted aliases;
- active snapshot, source revision, manifest hash, and corpus hash;
- coverage and gap health;
- ranked architecture cards and H2 sections;
- public interfaces, dependency paths, safe edit points, and risk areas;
- exact versioned evidence IDs, hashes, selection reasons, and evidence class;
- token estimate, omitted count, trace ID, and degraded reasons.

## Proven architecture lineage

The implementation consolidates three working systems:

- Atlas / `kg-factory`: fenced `ai_card` YAML, Markdown-AST H2 chunking,
  idempotent ingestion, PostgreSQL graph records, and visible gap nodes.
- NLKE Declarum Game Engine: the fleet-standard 13 declaration slots, root
  frontmatter, lint/scaffold/staleness operations, minimal boot context, and
  evidence-shaped answers.
- Command Center: repository-aware declared retrieval, persistent embeddings,
  bounded context compilation, immutable handoffs, MCP transport parity, and
  Codex lifecycle hooks.

The adopted contract keeps the strengths while correcting known limitations:
relationships are materialized only from explicit declarations, source
versions are immutable, repository identity never falls back to an unfiltered
search, and freshness uses hashes and revisions instead of filesystem mtime.

## Repository manifest

`.command-center/architecture.yaml` is the only local discovery authority. It
contains a stable ID, display name, aliases, selected Markdown roots and
patterns, exclusions, and accepted declaration dialects. It contains no token,
host, credential, local absolute path, or document body.

The scanner:

- discovers the repository root from nested working directories;
- accepts Markdown only;
- rejects traversal and symlink escape;
- caps documents at 1,000, each file at 512 KiB, and the corpus at 20 MiB;
- sorts source URIs deterministically;
- records the Git revision when available.

## Declaration dialects

Two source dialects normalize to one strict provider-neutral
`ArchitectureCard`:

1. root YAML frontmatter, used by the Declarum architecture;
2. a fenced YAML block with top-level `ai_card`, used by Atlas.

If a file contains both, the normalized declarations must be identical.
Missing cards are visible coverage gaps. Partial, malformed, conflicting, or
repository-mismatched cards reject activation when unsafe. Scalars that are
allowed as lists normalize without mutating the parsed input.

The fleet declaration slots are:

`kind`, `audience`, `status`, `owner_area`, `main_files`,
`public_interfaces`, `provides`, `depends_on`, `safe_edit_points`,
`risk_areas`, `graph_rag_entities`, `last_verified`, plus stable `id`,
`repository`, and human `title`.

## Explicit sync and health

Architecture upload is never a model or hook side effect.

```sh
python3 plugins/codex-command-center/scripts/architecture.py lint .
python3 plugins/codex-command-center/scripts/architecture.py status .
python3 plugins/codex-command-center/scripts/architecture.py sync .
```

- `lint` sends document bodies for stateless validation but does not persist.
- `status` sends only source URIs and SHA-256 hashes.
- `sync` shows repository, revision, document count, and bytes, then requires
  explicit confirmation before sending selected Markdown bodies.
- SessionStart invokes `status`, never `sync`.

Health reports coverage, missing/invalid/conflicting cards, local drift,
manifest or revision mismatch, unresolved/ambiguous relationships, embedding
coverage, and explicit degraded reasons.

## Versioned storage

Application migration 5 adds:

- `architecture_repositories`;
- `architecture_snapshots`;
- `architecture_document_versions`;
- `architecture_sections`;
- `architecture_section_embeddings`;
- `architecture_edges`;
- `architecture_issues`.

Sync first builds a staging snapshot. A valid snapshot activates
transactionally and moves the prior active snapshot to historical. Invalid
snapshots are rejected without replacing the current active snapshot.
Re-syncing the same corpus is idempotent. Historical document and section IDs
remain resolvable, so a published handoff cannot silently change meaning.

Typed relationships include `CONTAINS`, `PART_OF`, `DESCRIBES`,
`OWNS_CONTRACT`, `PROVIDES`, `DEPENDS_ON`, `SAFE_EDIT_POINT`, `RISK_AREA`, and
`MENTIONS`. Unresolved targets remain explicit issues rather than invented
edges.

## Shared compiler and task flow

Boot mode favors architecture indexes, repository orientation, implemented
cards, and overview/contract sections. Task mode ranks declared fields and
sections against the current request. Dense section retrieval is optional; if
it is unavailable, lexical and declared ranking continue with
`dense_architecture_retrieval_unavailable`.

Every budget applies to the fully serialized packet, including provenance. A
small budget removes lower-ranked receipts and their payload together; it does
not leave uncited prose.

Aria emits both the durable `context_pack` and the versioned
`architecture_brief` before answering. Handoff creation copies the exact brief
into the draft. Publication makes it immutable. `load_handoff` verifies the
active repository by registered ID, name, or alias and records a separate
activation. A later sync affects new task packs but not the published packet.

Codex Command Center v0.4 uses:

- SessionStart: local hash-only check plus boot ArchitectureBrief;
- UserPromptSubmit: `command-center-task-pack-v2`, containing the task brief
  and separately labelled durable context;
- human-readable model context with snapshot, receipts, interfaces, selected
  sections, safe points, risks, degraded reasons, and omissions;
- no unfiltered fallback when a repository is unknown.

## Evidence and graph visualization

`get_evidence` resolves versioned documents (`adoc_`), sections (`asec_`),
issues (`aissue_`), edges (`aedge_`), legacy declared documents, and durable
memory. `walk_dependencies` keeps snapshot provenance.

The browser graph shows declared repositories, versioned cards, capabilities,
selected handoffs, and audited Codex activations. Violet represents declared
structure, cyan the selected/active context path, and amber human-confirmed
durable memory. A historical source pinned by a handoff remains visible even
after a new snapshot activates.

## Operating boundaries

- Architecture content is instructions and evidence, never executable code.
- A client receives only selected context for its current repository and task.
- Voice may publish bounded context but cannot sync a repository, edit code,
  install tools, deploy, or confirm durable memory.
- Codex may propose a pending memory write; only the authenticated browser can
  confirm it.
- Tokens never enter the manifest, repository, handoff, URL, or logs.

## Verification

The automated suite covers both declaration dialects, duplicate headings,
path/corpus bounds, coverage gaps, rejection and activation, idempotency,
historical evidence, alias isolation, packet bounds, pinned handoffs, MCP
evidence, graph activations, stdio/HTTP schema parity, and plugin output.

The PostgreSQL behavioral test performs real migrations, activates two
snapshots, resolves historical evidence, re-instantiates the adapter, and
retrieves the active brief before dropping its test schema. See
[PostgreSQL under proot](postgresql-proot.md).
