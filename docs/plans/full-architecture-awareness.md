---
id: command-center.full-architecture-awareness.plan
repository: Command Center
title: Full Architecture Awareness Implementation Plan
kind: implementation_plan
audience:
  - engineer
  - ai_agent
  - evaluator
status: implemented
owner_area: declared context
main_files:
  - services/memory/aria_memory/documents.py
  - services/memory/aria_memory/context.py
  - services/memory/aria_memory/mcp.py
  - services/memory/aria_memory/db.py
  - services/memory/aria_memory/postgres.py
  - plugins/codex-command-center
  - apps/web/app/page.tsx
public_interfaces:
  - "POST /api/v1/architecture/sync"
  - "POST /api/v1/architecture/check"
  - "GET /api/v1/architecture/health"
  - "POST /api/v1/architecture/brief"
  - "build_task_pack"
  - "load_handoff"
provides:
  - phased implementation plan for shared Aria and Codex architecture awareness
  - versioned architecture snapshots and evidence receipts
  - Codex plugin architecture sync and context upgrade
depends_on:
  - command-center.full-architecture-awareness.research
  - command-center.declared-context
  - command-center.codex-plugin
safe_edit_points:
  - additive app migration
  - canonical declaration parser
  - architecture brief compiler
  - plugin helper and hook rendering
risk_areas:
  - cross-repository context leakage
  - mutable evidence cited by immutable handoffs
  - implicit repository upload
  - oversized hook packets
graph_rag_entities:
  - ArchitectureSnapshot
  - ArchitectureDocumentVersion
  - ArchitectureSection
  - ArchitectureEdge
  - ArchitectureIssue
  - ArchitectureBrief
last_verified: 2026-07-18
dimensions:
  inspectability: 1.0
  implementation_maturity: 1.0
  evidence_strength: 1.0
  operational_risk: 0.65
  decision_relevance: 1.0
---

# Full Architecture Awareness Implementation Plan

## Progress

- 2026-07-18: Phase 1 implementation started. The isolated architecture package
  now contains the canonical dual-dialect card model, parser, AST H2 chunker,
  lint report, and scaffold generator. Synthetic frontmatter and fenced-card
  fixtures exercise the two proven source conventions. Persistence remains on
  the existing document ingester until Phase 2 migrations are complete.
- 2026-07-18: Phase 2 persistence completed. Ordered application migration 5
  adds canonical snapshots, immutable document versions, sections, typed edges,
  issues, and section-embedding storage for SQLite and PostgreSQL. Activation
  is transactional and idempotent; rejected snapshots do not replace the
  active snapshot, and historical evidence remains byte-resolvable.
- 2026-07-18: Phase 3 explicit repository sync and health completed. A
  repository manifest bounds the Markdown corpus; authenticated lint is
  stateless, status sends hashes only, and sync requires an explicit plugin
  confirmation. Architecture health reports coverage gaps, drift, repository
  mismatch, and unresolved relationships. The plugin bundle validates and the
  full Python suite passed 79 tests at that boundary.
- 2026-07-18: Phases 4 and 5 completed. One bounded ArchitectureBrief now feeds
  Aria SSE, handoffs, HTTP/stdio MCP, and Codex Command Center v0.3. Published
  handoffs retain their original snapshot and evidence after a later sync.
  Registered aliases pass the repository guard; unknown repositories never
  trigger unfiltered fallback. The plugin uses hash-only SessionStart checks,
  readable source receipts, and user-home token storage.
- 2026-07-18: Phase 6 completed. The browser shows architecture snapshot,
  revision, coverage, source hashes, omissions, and degraded state. The graph
  includes versioned architecture evidence, pinned historical sources,
  handoff-selection relationships, and audited activation entering Codex.
- 2026-07-18: Phase 7 PostgreSQL behavior completed under Ubuntu PRoot. The
  first real migration exposed a command-result row-factory bug; the fix passed
  migration, two-snapshot activation, historical evidence, adapter restart,
  and brief retrieval before and after a clean PostgreSQL server restart.
- 2026-07-18: Phase 8 documentation completed. Twenty-two manifest-selected
  Markdown documents validate as architecture cards at 100% coverage. The
  manuals now describe the shared compiler, plugin v0.3, snapshot lifecycle,
  PostgreSQL procedure, security boundaries, evaluation, and next deployment
  gates. Project licensing moved to Apache-2.0 while retaining the author's
  same-source MIT upstream notices.
- 2026-07-18: Release-candidate verification completed: 85 ordinary Python
  tests passed with the explicitly environment-gated PostgreSQL test skipped;
  the real PostgreSQL contract passed separately before and after restart.
  Evaluation, web typecheck, 11 component tests, production web build, plugin
  validation, compilation, security scan, diff check, and 22/22 architecture
  card validation passed. Docker, installed-plugin cache refresh, `gcloud`, and
  deployed browser smokes are correctly retained as laptop/Cloud Build gates.

## Outcome

One user-initiated architecture sync makes a repository's declared architecture
available to both Aria and Codex. Command Center validates and versions the
declarations, indexes sections and typed relationships, reports gaps and
freshness, and compiles a bounded task-specific `ArchitectureBrief`.

The same brief is used by:

- Aria and Sol while preparing a plan;
- the immutable published handoff;
- remote and stdio MCP handlers;
- the Codex `SessionStart` and `UserPromptSubmit` hooks.

The user-visible promise is:

> Sync the architecture once. Plan with Aria. Continue in Codex with the same
> repository understanding and evidence receipts.

## Architectural decisions

### 1. Full means queryable, not always loaded

The whole declared corpus is indexed. Each request loads only a boot manifest,
relevant cards, relevant sections, and exact source receipts within a declared
token budget.

### 2. Declaration wins over inference

Every evidence item is labelled:

- `declared`: copied from a validated architecture card;
- `derived`: produced deterministically from structure or path normalization;
- `inferred`: produced by a model or heuristic;
- `verified`: checked against source content at a recorded hash or revision.

Inferred relationships never silently become declared graph edges.

### 3. Sync is explicit

The paired plugin may scan and hash only manifest-declared documentation paths.
Uploading document content requires an explicit `architecture sync` command or
equivalent browser approval. Session hooks may check hashes but do not silently
upload a checkout.

### 4. Published evidence is immutable

The latest document projection remains convenient for recall, but every sync
creates a versioned snapshot. A published handoff pins the snapshot and exact
document/section versions. Later syncs cannot change what an old handoff cited.

### 5. One compiler and one graph

Aria, REST, MCP, hooks, handoffs, and the browser call the same architecture
service and compiler. The browser visualizes the semantic graph; it does not
maintain a second architecture store.

### 6. Keep the MCP surface small

Do not add model-writable ingestion tools. Upgrade the existing tools:

- `build_task_pack` returns the task ArchitectureBrief;
- `recall_context` searches cards, sections, and durable memory;
- `get_evidence` resolves versioned cards, sections, issues, and memory;
- `walk_dependencies` traverses typed, provenance-preserving edges;
- `load_handoff` returns the pinned snapshot and activation receipt.

Architecture sync and health are authenticated application/plugin operations,
not autonomous model actions.

## Repository declaration

Add a safe, provider-neutral repository file:

```yaml
# .command-center/architecture.yaml
schema_version: 1
repository:
  id: command-center
  name: Command Center
  aliases:
    - command-center-v3
documents:
  roots:
    - docs
  patterns:
    - "**/*.md"
  exclude:
    - "archive/**"
dialects:
  - frontmatter
  - fenced-ai-card
```

The manifest contains paths and identities only. It must never contain a token,
host credential, local absolute path, or private source value.

The sync helper rejects:

- paths escaping the repository;
- symlink traversal outside the repository;
- undeclared file extensions;
- files above the configured size bound;
- batches above the count/byte quota;
- conflicting repository identity;
- secrets detected in manifest fields.

## Canonical declaration contract

Support both proven dialects:

1. YAML frontmatter whose root contains the 13 fields.
2. The first fenced YAML block whose root contains `ai_card`.

Normalize into:

```text
id
kind
audience[]
status
owner_area
main_files[]
public_interfaces[]
provides[]
depends_on[]
safe_edit_points[]
risk_areas[]
graph_rag_entities[]
last_verified
```

Command Center extensions remain optional:

```text
repository
title
dimensions
relationships[]
```

Rules:

- scalar-or-list fields normalize to lists;
- normalization never mutates the raw parsed card;
- stable declared IDs are preferred;
- missing IDs receive deterministic degraded IDs;
- malformed or missing cards produce issues rather than disappearing;
- a file containing both dialects must declare identical normalized values or
  fail with `conflicting_declarations`;
- Markdown sections are derived with an AST, never a heading regex;
- source URIs remain repository-relative;
- all stored records include dialect, content hash, snapshot ID, and source
  revision when available.

## Persistence model

Increment the independent application migration version. Keep memory row schema
version 1.

### New tables

`architecture_snapshots`

```text
id
repository
source_revision
manifest_hash
corpus_hash
status: staging | active | historical | rejected
document_count
valid_count
issue_count
created_at
activated_at
```

`architecture_document_versions`

```text
id
snapshot_id
stable_id
source_uri
dialect
title
declaration_json
body
content_hash
last_verified
created_at
UNIQUE(snapshot_id, source_uri)
```

`architecture_sections`

```text
id
document_version_id
stable_id
heading
heading_slug
ordinal
body
content_hash
evidence_class
UNIQUE(document_version_id, ordinal)
```

`architecture_section_embeddings`

```text
section_id
content_hash
provider
model
dimensions
vector
updated_at
```

`architecture_edges`

```text
id
snapshot_id
source_id
target_ref
target_id
relation_type
evidence_class
resolution_status: resolved | unresolved | ambiguous
source_document_version_id
source_field
created_at
```

`architecture_issues`

```text
id
snapshot_id
source_uri
code
severity: info | warning | error
detail_json
evidence_class
created_at
```

### Existing compatibility index

The versioned snapshot tables are canonical. Keep `documents` and
`document_embeddings` unchanged as the current compatibility index until
Phase 4 moves retrieval to active-snapshot joins. The existing
`documents.source_uri` is globally unique, so it cannot safely represent two
repositories that both contain a path such as `docs/architecture.md`.

Activate a new canonical snapshot in one transaction:

1. validate the complete staging snapshot;
2. create version records, sections, edges, and issues;
3. update embeddings for changed sections when section indexing is enabled;
4. mark the previous active snapshot historical;
5. mark the new snapshot active.

A rejected sync never changes the active snapshot. Phase 4 adapts document
recall and graph assembly to the canonical versioned tables, after which the
compatibility index can be retired through a separately verified migration.

### Migration behavior

Replace the current “create everything and record one version” behavior with
ordered, idempotent application migrations. Tests must begin from both an empty
database and the existing version-4 schema. SQLite and PostgreSQL must expose
the same table, constraint, cascade, and transaction behavior.

## Typed graph materialization

Create only relationships supported by declarations or deterministic
structure:

| Source | Relation | Target | Evidence |
|---|---|---|---|
| repository | `CONTAINS` | document | derived |
| section | `PART_OF` | document | derived |
| document | `DESCRIBES` | `main_files` path | declared |
| document | `OWNS_CONTRACT` | public interface | declared |
| document | `PROVIDES` | capability/entity | declared |
| document | `DEPENDS_ON` | document/entity reference | declared |
| document | `SAFE_EDIT_POINT` | safe-edit record | declared |
| document | `RISK_AREA` | risk record | declared |
| document | `MENTIONS` | graph-RAG entity | declared |

`CALLS`, `PERSISTS_TO`, and other extended relationships are materialized only
from the optional explicit `relationships` list. Prose can contribute search
text, but it cannot create a declared edge.

Preserve unresolved references. They are architecture-health findings and
useful evidence, not ingestion failures.

## Architecture health

`ArchitectureHealth` contains:

```text
repository
snapshot_id
source_revision
last_sync
documents_scanned
valid_cards
coverage
missing_cards[]
invalid_cards[]
conflicts[]
stale_sources[]
unresolved_edges[]
ambiguous_edges[]
embedding_coverage
degraded
degraded_reasons[]
```

Freshness uses multiple signals:

- current local content hashes compared with the active snapshot;
- source revision compared with the snapshot revision;
- `last_verified` age;
- missing or renamed sources;
- embedding content-hash coverage.

Filesystem modification time may be shown as a hint but is never the sole
freshness decision.

## ArchitectureBrief contract

Add two request modes:

- `boot`: small repository orientation for session start;
- `task`: prompt-specific architecture for planning or editing.

The response contains:

```text
schema_version
mode
repository_identity
snapshot_receipt
health_summary
subsystems[]
documents[]
sections[]
interfaces[]
dependency_paths[]
safe_edit_points[]
risk_areas[]
architecture_issues[]
sources[]
token_estimate
token_budget
omitted_candidate_count
degraded
degraded_reasons[]
trace_id
```

Each `source` includes its stable ID, version ID, source URI, evidence class,
content hash, score, selection reasons, and optional section anchor.

Compilation order:

1. resolve an exact registered repository or declared alias;
2. select its active snapshot;
3. classify task intent;
4. retrieve latest cards and section chunks;
5. expand only bounded typed dependency paths;
6. fuse declared, lexical, structural, dense, and durable-memory candidates;
7. render receipts and health findings;
8. remove lowest-ranked sources until serialized output fits the token budget.

Unknown repositories return a visible `repository_unregistered` degraded brief.
They must not fall back to unfiltered cross-repository evidence.

## API operations

### `POST /api/v1/architecture/sync`

Authenticated, explicit content sync from the pairing helper or approved UI.
Accepts the manifest identity, source revision, and bounded document batch.
Returns snapshot ID, corpus hash, ingest counts, issues, and activation status.

### `POST /api/v1/architecture/check`

Accepts only repository identity, revision, manifest hash, and local content
hash inventory. Returns drift without uploading document bodies. This is safe
for `SessionStart`.

### `GET /api/v1/architecture/health`

Returns the active snapshot health for an exact repository identity.

### `POST /api/v1/architecture/brief`

Builds `boot` or `task` ArchitectureBrief. The existing context-pack endpoint
may delegate to this compiler while retaining its compatibility response during
the migration.

### `GET /api/v1/architecture/evidence/{id}`

Resolves versioned documents, sections, issues, and graph receipts. Existing
document and memory evidence routes remain supported.

## Phase 1 — Parser, contract, and tests

Create:

- `services/memory/aria_memory/architecture/models.py`
- `services/memory/aria_memory/architecture/parser.py`
- `services/memory/aria_memory/architecture/chunking.py`
- `services/memory/aria_memory/architecture/lint.py`
- `services/memory/tests/test_architecture_parser.py`

Change:

- `services/memory/frontmatter_rag/presets.py`
- dependency metadata for the Markdown AST parser and YAML loader;
- the synthetic fixtures to cover both dialects.

Tests:

- both dialects normalize identically;
- audience and every list slot normalize defensively;
- the raw card is unchanged;
- non-card YAML fences are ignored;
- dual declarations must agree;
- H2 markers inside code fences do not split;
- repeated headings receive deterministic unique section IDs;
- missing and malformed cards produce typed issues;
- path traversal and oversize input fail closed.

Exit gate:

- one canonical parser passes the Atlas and game-engine behavioral cases without
  importing either repository at runtime.

## Phase 2 — Versioned persistence and graph

Create:

- `services/memory/aria_memory/architecture/store.py`
- ordered app migration helpers;
- SQLite and PostgreSQL schema migrations for snapshots, versions, sections,
  edges, issues, and section embeddings.

Change:

- `db.py`
- `postgres.py`
- `documents.py` to act as the compatible latest projection;
- `models.py`
- `app.py` graph assembly.

Tests:

- empty database migration;
- upgrade from version 4;
- snapshot transaction rollback;
- idempotent corpus re-sync;
- new snapshot for changed content;
- immutable historical document versions;
- section replacement without orphan records;
- typed edge resolution and visible unresolved references;
- PostgreSQL/SQLite behavioral parity.

Exit gate:

- a published snapshot remains byte-identical and resolvable after a newer
  snapshot is activated.

## Phase 3 — Repository sync and health

Create:

- `.command-center/architecture.yaml` for Command Center itself;
- `plugins/codex-command-center/scripts/architecture.py`;
- architecture sync/check/health API handlers;
- plugin-local hash inventory cache under the user state directory.

The helper supports:

```text
architecture.py lint [repository]
architecture.py status [repository]
architecture.py sync [repository]
architecture.py scaffold [path]
```

`sync` prints the exact repository, document roots, file count, and byte count
before upload and requires explicit confirmation unless `--yes` is provided by
the user. No model-facing tool passes `--yes`.

Tests:

- manifest validation;
- symlink and traversal rejection;
- dry-run/lint with no writes;
- hash-only check sends no bodies;
- explicit sync activates a snapshot;
- invalid batches do not partially activate;
- repository alias resolution;
- token and document content redaction in errors/logs;
- plugin helper works from nested working directories.

Exit gate:

- a clean checkout can pair, lint, sync, and receive the same snapshot receipt
  from local SQLite or hosted PostgreSQL.

## Phase 4 — Shared brief and handoff pinning

Create:

- `services/memory/aria_memory/architecture/retrieval.py`
- `services/memory/aria_memory/architecture/compiler.py`
- `ArchitectureBrief` and related models.

Change:

- `context.py` to delegate declared architecture selection;
- `toolbox.py` so handoffs pin snapshot and evidence-version receipts inside
  `architecture_json`;
- `mcp.py` tool handlers and evidence resolution;
- Aria agent tool descriptions and prompt framing.

Tests:

- boot versus task packet size;
- section-level retrieval;
- declared and durable-memory fusion;
- exact repository or alias matching;
- no cross-repository fallback;
- missing dense provider yields byte-stable declared/lexical selection with
  degraded metadata;
- token bound measures the fully serialized packet;
- handoff publication pins snapshot ID, corpus hash, and versioned sources;
- loading after a later sync still resolves the original evidence;
- repository mismatch remains a hard failure;
- screenshot findings remain labelled as inferences.

Exit gate:

- Aria planning and `load_handoff` cite the same snapshot and evidence versions.

## Phase 5 — Codex Command Center plugin upgrade

Target repository release: `0.3.0` before applying a local Codex cachebuster.

Change:

- `.codex-plugin/plugin.json`
- `hooks/hooks.json`
- `scripts/client.py`
- `scripts/hook.py`
- `scripts/health.py`
- `scripts/mcp_server.py`
- `.mcp.json`
- plugin README and migration guide.

Behavior:

- pairing offers the explicit architecture lint/sync next step;
- health reports pairing, transport, repository registration, snapshot,
  freshness, and degraded retrieval separately;
- `SessionStart` performs a hash-only check and injects a compact boot brief;
- `UserPromptSubmit` injects the task brief;
- both hook outputs use a compact human-readable receipt renderer instead of an
  unlabelled raw JSON blob;
- injected context states snapshot ID, evidence IDs, omissions, health, and
  degraded reasons;
- `load_handoff` instructions require Codex to summarize the injected snapshot
  and begin the interview before editing;
- stdio forwards the canonical remote schemas/results so it cannot drift from
  the HTTP MCP contract;
- an unavailable Command Center produces a concise degraded message and does
  not block Codex from working locally;
- unknown repository identity cannot trigger unfiltered workspace retrieval.

Plugin validation:

1. run the repository plugin tests;
2. run the official plugin validator;
3. smoke-test initialize, tools/list, and tools/call over stdio;
4. compare stdio and HTTP schemas and structured results;
5. update the installed development copy with the plugin cachebuster helper;
6. reinstall from the confirmed local marketplace;
7. start a new Codex thread for hook/tool pickup.

Do not hand-edit a marketplace file during the update loop.

Exit gate:

- a fresh Codex thread displays the boot snapshot receipt, loads a handoff,
  cites versioned evidence, and asks the first architecture-aware interview
  question before any edit.

## Phase 6 — Interface and Aria experience

Add architecture health to repository selection and Handoff Builder:

- last synced revision and time;
- coverage and valid-card count;
- stale, missing, conflicting, and unresolved declarations;
- explicit **Sync architecture** guidance;
- included cards/sections and omitted candidates;
- pinned snapshot and corpus hash in the exact Codex packet.

Extend the graph:

- violet document, section, interface, file, capability, safe-edit, and risk
  nodes;
- cyan selected ArchitectureBrief nodes and animated activation edges;
- amber confirmed durable memory;
- visible relation type, evidence class, source ID, and snapshot receipt.

Aria:

- can navigate health findings and explain the current snapshot;
- can recommend syncing stale architecture;
- can prepare a handoff from the active snapshot;
- cannot initiate repository upload, edit documentation, or confirm durable
  memory;
- remains active while minimized.

Tests:

- health states and receipts render;
- graph filtering preserves active dependency paths;
- voice can open health/evidence and narrate degraded state;
- voice cannot invoke sync;
- Handoff Builder shows the exact pinned packet before publication;
- mobile screenshot upload/paste and minimized Aria remain functional.

Exit gate:

- the user can see exactly what Aria and Codex know, what they do not know, and
  which snapshot supplied it.

## Phase 7 — PostgreSQL, proot, and deployment

Local contract validation:

1. enter Ubuntu with `proot-distro login ubuntu`;
2. use the proven PostgreSQL/pgvector installation pattern from Atlas;
3. bind PostgreSQL to loopback and a non-conflicting port;
4. run migrations and the PostgreSQL contract suite;
5. restart PostgreSQL and repeat snapshot activation/brief retrieval;
6. run the container smoke test against the loopback database.

Production:

- Cloud SQL PostgreSQL stores workspaces and architecture snapshots;
- Cloud Run remains stateless and scale-to-zero safe;
- Secret Manager holds OpenAI and signing credentials;
- structured logs contain IDs, counts, hashes, latency, and degraded codes but
  never document bodies, prompts, tokens, or screenshots;
- staging verifies authenticated MCP initialization and a full architecture
  sync/brief/handoff lifecycle;
- production deployment uses a saved, reproducible repository revision.

Fallback:

- push the verified public repository;
- pull it on the laptop;
- install a fresh Codex and Codex Command Center plugin;
- pair and sync the repository architecture;
- run Cloud Build and deploy from the clean checkout.

This fallback is also a portability demonstration, not a second architecture.

## Phase 8 — Full documentation update

No feature is complete until the documentation reflects the verified
implementation.

Update:

- `README.md`
- `docs/quickstart.md`
- `docs/user-guide.md`
- `docs/architecture.md`
- `docs/declared-context.md`
- `docs/api-mcp.md`
- `docs/handoffs.md`
- `docs/codex-plugin.md`
- `docs/aria-voice.md`
- `docs/capability-authoring.md`
- `docs/graph-canvas.md`
- `docs/security-privacy.md`
- `docs/cloud-run.md`
- `docs/deployment-checklist.md`
- `docs/troubleshooting.md`
- `docs/eval-report.md`
- `docs/build-week-log.md`
- `docs/demo-script.md`
- `docs/roadmap.md`
- `plugins/codex-command-center/README.md`
- `plugins/codex-command-center/MIGRATION.md`

Add:

- architecture manifest and card authoring manual;
- both supported declaration dialects;
- lint, status, sync, and scaffold reference;
- snapshot and evidence-version lifecycle;
- ArchitectureBrief schema and examples;
- architecture health codes and remediation;
- plugin architecture-sync and reinstall guide;
- PostgreSQL under proot guide;
- reproducible architecture-awareness evaluation;
- provenance report describing which patterns came from Atlas, NLKE Declarum,
  and Command Center;
- updated architecture and data-flow diagrams.

Documentation rules:

- distinguish implemented, verified, degraded, and planned behavior;
- use synthetic public examples;
- never include local absolute paths, tokens, access codes, private prompts, or
  database contents;
- credit the MIT-licensed Cloud Run/MCP deployment patterns already identified;
- describe the author accurately as a self-taught context/knowledge engineer
  consolidating independently working systems.

Exit gate:

- a new user can install, pair, author or adopt cards, sync architecture, prepare
  a handoff with Aria, load it in Codex, understand every receipt, and
  troubleshoot degraded state without undocumented steps.

## Phase 9 — Ingest the finished architecture, commit, and push

The documentation is part of the product's architecture data, not a release
afterthought. Close the implementation loop in this exact order:

1. finish the code, plugin, tests, and complete documentation update;
2. lint the finished Command Center architecture corpus;
3. explicitly sync the finished corpus into Command Center;
4. record the new active snapshot ID, source revision, corpus hash, coverage,
   and health findings;
5. ask Aria for a repository boot brief and a task ArchitectureBrief;
6. load the same snapshot through the upgraded Codex plugin;
7. verify Aria and Codex cite the same versioned architecture evidence;
8. run the full Python, web, typecheck, production build, plugin, container, and
   PostgreSQL verification suite;
9. review the complete working-tree diff, including pre-existing changes, so
   the commit contains the intended finished product and no secrets or local
   artifacts;
10. create the full implementation commit;
11. push the verified commit to the public GitHub repository;
12. confirm the remote branch contains that exact commit before planning or
    executing the next phase.

The snapshot compiled before the Git commit may initially carry a working-tree
corpus hash. After committing, perform a final hash-only check or sync so the
active architecture receipt records the exact pushed source revision. If that
creates a new snapshot, repeat the Aria/Codex receipt comparison against the
commit-pinned snapshot.

The push is an explicit release operation authorized by the project owner, but
it must happen only after validation. Do not push an intermediate planning-only
state as the completed architecture-awareness release.

Exit gate:

- the remote repository, Aria's active architecture snapshot, and Codex's
  loaded snapshot all identify the same verified source revision and corpus;
- a clean laptop checkout can reproduce plugin installation, architecture sync,
  tests, and deployment without relying on uncommitted device state.

## Verification matrix

### Python

- parser dialect, normalization, lint, AST chunking, and issue tests;
- snapshot, versioning, graph edge, health, freshness, and rollback tests;
- ArchitectureBrief retrieval, bounding, provenance, and degraded tests;
- handoff snapshot immutability and activation-audit tests;
- authentication, repository isolation, redaction, and log-safety tests;
- SQLite/PostgreSQL migration and behavioral-contract tests;
- remote MCP initialize/tools/list/tools/call and restart tests;
- stdio/HTTP schema and result parity;
- plugin helper and hook output tests.

### Web

- architecture health and repository selection;
- included/omitted evidence inspector;
- pinned snapshot receipt in Handoff Builder;
- typed graph relation and activation rendering;
- voice navigation and publication boundaries;
- screenshot upload/paste;
- minimized Aria;
- mobile layout and browser interaction.

### End to end

1. fresh checkout with a declared manifest;
2. pair Codex Command Center;
3. lint and explicitly sync architecture;
4. Aria retrieves the active snapshot;
5. upload a screenshot and describe a redesign;
6. Sol recommends the architecture-aware redesign capability;
7. inspect and publish the pinned handoff;
8. start Codex in the same checkout;
9. SessionStart reports matching local/cloud hashes;
10. run the emitted `/plan` command;
11. Codex loads the handoff, cites versioned evidence, and asks the first
    informed interview question before editing.

Repeat with:

- dense retrieval unavailable;
- one stale card;
- one missing card;
- one unresolved dependency;
- repository mismatch;
- service restart/cold start;
- SQLite and PostgreSQL.

## Evaluation

Run the same repository redesign task under:

1. no Command Center;
2. ordinary durable memory context;
3. latest unversioned document context;
4. full versioned architecture handoff.

Measure:

- repository reads and searches before a useful plan;
- tokens and elapsed time;
- required architecture evidence retained;
- unsupported or uncited claims;
- stale-context detection;
- safe edit points and risks retained;
- dependency-path accuracy;
- number and quality of interview questions;
- agreement between Aria's plan evidence and Codex's loaded evidence.

The strongest result is not “fewest reads at any cost.” It is faster arrival at
an evidence-supported plan with fewer unsupported assumptions.

## Suggested implementation sequence

Use small verification boundaries:

1. parser and fixture commit;
2. migrations and snapshot store commit;
3. typed graph and health commit;
4. explicit sync helper/API commit;
5. ArchitectureBrief compiler commit;
6. handoff pinning and MCP contract commit;
7. Codex plugin `0.3.0` commit;
8. interface and Aria integration commit;
9. proot/PostgreSQL and container verification commit;
10. complete documentation/evaluation commit;
11. ingest and verify the commit-pinned architecture snapshot;
12. push the verified release commit and confirm the remote revision.

Do not mix the existing unrelated working-tree changes into destructive cleanup
or reset operations. Review overlapping files before every patch.

## Definition of done

Full architecture awareness is complete when:

- both declaration dialects ingest into one validated contract;
- sections and typed declared relationships are queryable;
- health exposes coverage, conflicts, staleness, and unresolved references;
- an explicit sync creates an immutable versioned snapshot;
- Aria and Codex receive the same bounded ArchitectureBrief;
- published handoffs retain byte-resolvable evidence after later syncs;
- repository mismatch cannot leak another repository's context;
- the upgraded plugin passes validation and works in a fresh thread;
- SQLite, PostgreSQL/proot, web, MCP, container, and mobile tests pass;
- the complete documentation set matches the verified behavior;
- the completed docs are ingested into Aria's active architecture snapshot;
- Aria and Codex cite the same commit-pinned snapshot after the final sync;
- the complete reviewed implementation is committed and pushed;
- the demo reaches the first informed Codex interview question without editing
  code or demonstrating another provider.
