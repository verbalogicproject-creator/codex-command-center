# NLKE-GCA Take a Step Back Architecture Exhibit

```yaml
ai_card:
  id: command-center.architecture-exhibit
  repository: Command Center
  title: NLKE-GCA Take a Step Back Architecture Exhibit
  kind: architecture
  audience: [users, judges, contributors, Aria, Codex]
  status: active
  owner_area: architecture awareness
  main_files: [docs/atlas/claims.json, scripts/build_atlas.py, apps/web/public/atlas/index.html]
  public_interfaces: [/atlas/index.html, product header link, claim-to-source explorer]
  provides: [progressive architecture explanation, generated backend inventory, claim grounding paths, project lineage, release receipt]
  depends_on: [command-center.nlke-gca, command-center.architecture-awareness, command-center.handoffs, command-center.aria-voice, command-center.security-privacy]
  safe_edit_points: [curated claim language, progressive story order, source mappings, responsive presentation]
  risk_areas: [stale generated output, unsupported public claims, private lineage disclosure, embedded secrets or local paths]
  graph_rag_entities: [NLKE-GCA, Take a step back, grounding, evidence, Grounding Receipt, Grounding Compiler, immutable handoff, Claim Source Explorer]
  last_verified: 2026-07-20
```

## Purpose

The application demonstrates the product. The architecture exhibit explains
why the product can make its claims and names the system:
[NLKE Grounded Continuity Architecture](nlke-gca.md). It starts with the small
Aria → Grounding Compiler → Codex loop, then progressively reveals:

1. four grounding layers;
2. the shared context compiler and immutable handoff;
3. safety classifications and human gates;
4. the bidirectional Claim ↔ Source explorer;
5. the complete generated backend inventory;
6. the timestamped research and project lineage.

The public exhibit is served at `/atlas/index.html`. It is a static build
artifact and does not query a workspace, database, model provider, or
deployment API. The explicit filename works consistently in Next development,
the exported site, and nginx.

## Grounding vocabulary

Use **grounding** for the user-facing product promise and **evidence** for an
individual supporting source:

- **grounding source**: one versioned document, memory, finding, capability,
  symbol, route, table, test, or receipt;
- **grounding packet**: the bounded context delivered to an agent;
- **grounding receipt**: the selected and omitted sources, versions, hashes,
  token estimate, and degraded reasons;
- **activation receipt**: proof that a client loaded a particular published
  handoff.

Existing `evidence_id`, `evidence_sources`, and API contract names remain
unchanged for compatibility.

## Generated truth contract

`docs/atlas/claims.json` is the curated narrative and claim map.
`scripts/build_atlas.py` extracts and validates:

- production Python modules and symbols;
- FastAPI methods, routes, and handlers;
- SQLite and PostgreSQL tables and migration level;
- backend regression tests;
- direct file, documentation, and TypeScript-controller references;
- source locations and bounded excerpts.

Every featured claim emits an `nlke-gca-grounding-receipt-v1` record and must
resolve to implementation sources and a regression
test. A missing file, symbol, route, table, needle, test, duplicate claim ID,
unknown grounding layer, or stale generated artifact fails the atlas gate.
The generator embeds a content hash over its inputs so the public receipt
describes the source snapshot rather than a hand-entered release count.

The canonical public artifact is
`apps/web/public/atlas/index.html`. The documentation mirror
`docs/command-center-atlas.html` is generated from the same bytes for
standalone repository viewing. Neither file is architecture-corpus input; this
Markdown card is the bounded awareness source.

## Claim and source lenses

The claim lens moves from plain-language promise to implementation:

```text
claim → route/controller → Python symbol → table/contract → test → failure behavior
```

The source lens reverses the relationship. Selecting a Python module, route,
table, test, or excerpt shows every featured claim it supports. The full
inventory remains available even when a source is not part of the judge fast
path, which keeps the main explanation small without hiding backend
complexity.

Source excerpts are deliberately bounded. The exhibit never embeds complete
private repositories, database rows, credentials, prompts, access codes, raw
screenshots, raw audio, WebRTC payloads, or local absolute paths.

## Four grounding layers

1. **Durable collaboration** — sessions, typed and spoken turns, facts,
   episodes, pending proposals, and receipts.
2. **Declared repository architecture** — architecture cards, H2 sections,
   graph edges, embeddings, health, gaps, and immutable snapshots.
3. **Human and visual intent** — role-labelled screenshots reduced to hashes,
   dimensions, labelled findings, unresolved choices, and an editable plan.
4. **Executable context** — trusted capabilities, the database-backed Aria
   command registry, active surface/workflow state, and bounded persona
   profiles.

The context compiler selects across these sources and reports omissions and
degraded reasons. Publication freezes the selected packet into an immutable,
repository-bound handoff. Loading creates a per-client activation receipt.

## Provenance boundaries

The origin story appears after the working architecture proof. It links to
Eyal Nof's June 13, 2025 OpenAI Community post as a timestamped artifact, not
as technical authority. Python NLKE, Atlas / `kg-factory`, Declarum, and ARIA
are labelled private lineage and link only to sanitized in-repository receipts.
Public repositories receive public links.

The exhibit describes Android/Termux as an engineering constraint: the product
was designed and shipped from Android/Termux, then verified through clean CI,
PostgreSQL, and Cloud Run. Private correspondence is excluded unless its
author explicitly approves publication.

## Build and release

Run:

```sh
python scripts/build_atlas.py
python scripts/build_atlas.py --check
```

CI uses `--check`; contributors must regenerate after a referenced
implementation, test, schema, narrative, or template change. For a release,
`ATLAS_RELEASE_REF` may select the exact public tag or commit used by source
links. The default is `main`, while the embedded snapshot SHA-256 still
verifies the exact extracted content.
