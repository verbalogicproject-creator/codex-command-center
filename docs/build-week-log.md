# Build Week log

```yaml
ai_card:
  id: command-center.build-week-log
  repository: Command Center
  title: Build Week Provenance Log
  kind: provenance_report
  audience: [evaluator, engineer, ai_agent]
  status: verified
  owner_area: submission
  main_files: [README.md, docs, services/memory, apps/web, plugins/codex-command-center]
  public_interfaces: [Build Week provenance]
  provides: [implementation chronology, tested provenance claims]
  depends_on: [command-center.architecture, command-center.eval-report]
  safe_edit_points: [append-only dated entries with evidence]
  risk_areas: [overclaiming unverified deployment or model behavior]
  graph_rag_entities: [Build Week, Command Center]
  last_verified: 2026-07-19
```

## 2026-07-18

- Established clean-room baseline. The planned v2 and `project_memory` sources
  were not present in the fresh workspace; provenance is recorded in
  `BASELINE.md`.
- Implemented row schema v1 plus independent app migrations.
- Added persistent embeddings, incremental sync, hybrid recall and 35-query eval.
- Added signed demo auth, quotas, isolated workspaces and typed HTTP contracts.
- Added GPT-5.6 direct-tool Aria loop and deterministic no-key fallback.
- Added human-gated proposal confirmation and append-only audit.
- Built the five-surface responsive Next.js UI and React Flow/Dagre graph.
- Integrated semantic evidence cards, active-context SVG pulse edges, and an
  accessible continuous surface dock using the proven Canvas OS visual patterns
  without importing its editor/runtime dependencies.
- Validated the Command Center Memory plugin end to end: six MCP tools, four
  declared hooks, normalized checkout-to-declared repository matching,
  deduplicated dependency walks, and a paired browser-workspace proposal that
  remained pending for human review.
- Added trusted repository-local Codex registration and aligned hook output with
  Codex's model-visible context protocol. Session and prompt hooks now inject
  bounded packets directly; Stop proposals are explicit opt-in because Codex
  emits Stop after every turn.
- Corrected project MCP startup to resolve the server and state directory from
  the Git root. Verified a real Codex 0.144.5 non-interactive thread bootstrap
  and added a nested-working-directory regression test.
- Passed Python, frontend typecheck, component test and Android Webpack build gates.

Codex session ID: unavailable in the execution environment.

Milestone commits:

- `e0a798a` — clean-room baseline and source-provenance boundary
- `e140418` — memory service, Aria, fixtures, interface, packaging and docs
- `a61401c` — generated build-state cleanup
- `d3eba06` — strict tools, conflict guard, persistent turns and runtime hardening

External submission work still requires repository credentials, a Google Cloud
project/secrets, a narrated video, and the `/feedback` session ID.

## Codex Command Center handoff milestone

- Added the persistent capability library with five verified provider-neutral
  built-ins, versioning, trust filtering, provenance hashes, repository scope,
  recommendation, and activation counts.
- Added validated/resized screenshot analysis with raw-image non-retention and
  explicit inference labels, plus an optional Sol Responses path and degraded
  local fallback.
- Added draft, immutable publication, new-version editing, revocation,
  repository-verified load, bounded packet construction, and activation audit.
- Added authenticated stateless `/mcp`, one-time token exchange, hash-only token
  persistence, revocation, and direct/stdio tool parity.
- Renamed and upgraded the end-user plugin to **Codex Command Center**, adding
  handoff tools, remote/local transport choices, pairing and health helpers, and
  migration guidance.
- Added Capability Library and Handoff Builder surfaces, exact packet receipts,
  voice publication, graph capability/handoff nodes, and the generated Codex
  `/plan` command.
- Added end-to-end capability, screenshot, handoff, auth, MCP, plugin, and web
  contract tests and completed the public manuals and demo script.

## Full architecture-awareness milestone

- Consolidated the working Atlas and NLKE Declarum patterns into one strict,
  provider-neutral declaration and retrieval contract.
- Added manifest-bounded dual-dialect parsing, Markdown-AST H2 chunking, lint,
  scaffold, drift health, transactional snapshots, immutable versions, typed
  explicit relationships, issues, and bounded ArchitectureBrief compilation.
- Integrated the same brief into Aria SSE, immutable handoffs, HTTP and stdio
  MCP, Codex Command Center v0.3 hooks, browser receipts, and the graph.
- Proved registered aliases without unfiltered fallback, old-handoff snapshot
  immutability after a new sync, historical evidence resolution, and audited
  activation entering Codex.
- Ran a real PostgreSQL 18 test under Ubuntu PRoot. Its first migration exposed
  a DDL row-factory defect; after the fix, the behavioral suite passed before
  and after a clean PostgreSQL restart, with no leftover workspace schemas.
- Declared every manifest-selected Markdown manual as an architecture card,
  producing 100% coverage before final Aria ingestion.
- Used the commit-pinned release ingestion as a functional gate, not just a
  document-count check. It exposed dependency paths surviving after their
  selected root documents were budget-evicted, which could leave a valid
  2,000-token packet with no evidence receipts. The compiler now removes those
  orphaned paths, retains the highest-ranked evidence, and has a full-corpus
  regression test.
- Verified the release corpus produces identical snapshot and source receipts
  through Aria's compiler and Codex's `build_task_pack` path.

The Cloud Run/MCP deployment patterns are credited to the author's
MIT-licensed `Claude-ToolBox-Curriculum` sibling project.

## 2026-07-19 — portable toolbox and deployment preparation

- Added the verified Taste-guided frontend redesign interview capability,
  including exact MIT provenance, content hashes, triggering situations,
  content-addressed built-in seeding, recommendation, handoff version pinning,
  and Codex MCP injection.
- Added the BYOK boundary: workspace-bound authenticated encryption, one-hour
  cryptographic expiry, an HttpOnly `/api/v1` browser-session cookie, immediate
  deletion, request-scoped Sol/Aria routing, Realtime client-secret minting,
  and no global public model key fallback.
- Added the visible **Connect OpenAI** receipt and removal flow. Retrieval,
  capabilities, handoffs, and MCP remain usable without a model credential.
- Split the web, API, and MCP container definitions. The MCP-only application
  now imports a shared workspace data plane rather than initializing browser or
  BYOK routes as a side effect.
- Added the three-image Cloud Build manifest and dry-run-first Artifact
  Registry cleanup policy. No Cloud SQL instance or Cloud Run workload was
  created during this preparation phase.
- Upgraded **Codex Command Center** to v0.4.0 and standardized MCP, hook, and
  helper launchers on `python3`, directly addressing Linux startup failures
  caused by a missing optional `python` alias.
- Verified the Termux Google Cloud SDK, authenticated project, required API
  enablement, and `me-west1` service compatibility. Cloud Build remains the
  container gate because this Android environment has no local Docker engine.

## 2026-07-19 — Taste workflow, voice tour, and plugin v0.5

- Added deterministic `command-center-redesign-suggestion-v1` SSE events with
  exact Taste version/hash, alternatives, architecture and evidence receipts.
- Added migration 6 and `command-center-planning-receipt-v1`; Sol receives only
  screenshot metadata/findings after analysis and falls back to a validated
  deterministic Taste Open Plan.
- Extracted the typed Handoff Controller used by buttons and Realtime voice.
  Voice can prepare and revise the visible draft but only the exact phrase
  **Approve this handoff.** may publish it.
- Added `command-center-tour-script-v1` with optional BYOK Luna narration,
  stable evidence-bound steps, explicit pauses, and deterministic fallback.
- Advanced Codex Command Center to v0.5.0. The exact generated `/plan` command
  now injects a directive requiring a visible `load_handoff` call and never
  secretly loads or substitutes an ordinary task pack.

## 2026-07-19 — live v0.5 staging

- Built and deployed web, API, and MCP from commit
  `9729ec3fb411ffba53e34c8578375bd5967544f0` with Cloud SQL PostgreSQL,
  separate runtime identities, per-secret IAM, a recurring approximately
  USD 50 budget, and no operator OpenAI key.
- The first MCP rollout exposed an eager package import that crossed the
  API-only BYOK boundary. Replaced it with a lazy API factory and added an
  isolated cloud-import regression test instead of granting MCP more secrets.
- The first hosted Taste query exposed psycopg interpreting literal percent
  characters as placeholders. The PostgreSQL adapter now escapes literals
  before translating portable parameters; the exact capability query passes
  against real PostgreSQL before and after a clean restart.
- Called all ten remote MCP tools, verified API/MCP schema parity, published and
  reloaded a screenshot-derived Taste handoff, exercised the seven-step tour,
  rejected pending-only synthetic writes, revoked and repaired a token, and
  forced fresh revisions of all three services without losing state.
