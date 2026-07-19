# Codex Command Center

> Plan with Aria. Continue in Codex. Bring your toolbox everywhere.

Codex Command Center is one provider-neutral cloud toolbox for coding sessions.
Aria accepts a repository, screenshot, and voice or text request. GPT‑5.6 Sol
combines screenshot inferences with declared repository evidence, recommends an
exact versioned capability, and builds an editable Open Plan. After explicit
publication, Codex loads the bounded handoff through MCP and begins an informed
interview before editing.

Codex is the primary client and competition focus. The hosted MCP contract is
portable to other compatible clients without changing the visible demo story.

## Implemented

- Full architecture awareness: a safe repository manifest, dual-dialect
  provider-neutral cards, Markdown-AST sections, transactional versioned
  snapshots, typed relationships, coverage/drift health, and one bounded
  `ArchitectureBrief` shared by Aria, handoffs, MCP, and Codex.
- Persistent, versioned capability library with six kinds, repository scope,
  tool references, trust filtering, provenance, content hashes, and activation
  counts.
- Six built-ins: Taste-guided frontend redesign interview, lightweight frontend
  redesign interview, mobile accessibility review, graph-canvas integration,
  evidence-bound coding plan, and safe deployment preparation.
- Screenshot validation, MIME sniffing, in-memory resize, SHA-256 receipts,
  optional Responses API multimodal analysis, inference labels, and zero raw
  image retention.
- Draft, immutable published, versioned, and revoked handoffs with exact
  capability pins, editable Open Plans, evidence receipts, risks, safe edit
  points, omissions, degraded metadata, and per-client activation audit.
- Stateless authenticated JSON-RPC MCP at `POST /mcp` plus a parity stdio
  adapter and ten capability, handoff, context, evidence, timeline, and
  pending-memory tools.
- One-time browser pairing exchanged for revocable workspace tokens; only token
  hashes are stored server-side.
- **Codex Command Center v0.4** plugin with remote/local MCP config, hash-only
  SessionStart drift checks, boot/task architecture briefs, four hooks,
  sanitized telemetry, pending Stop proposals, pairing and architecture
  helpers, repository isolation, and migration from `command-center-memory`.
- Capability Library and Handoff Builder surfaces, graph capability/handoff
  nodes, active-handoff edges, voice publication, exact packet preview, and
  generated `/plan` command.
- Existing inspectable memory, declared retrieval, evidence graph, Aria chat and
  Realtime navigation, human-gated durable memory, and append-only audit.

No native skill installation, arbitrary code distribution, dynamic tool
installation, deployment control, or voice/Codex memory confirmation is claimed.

## Five-minute start

Requires Python 3.12+ and Node 22+.

```sh
cp .env.example .env
scripts/setup.sh
scripts/dev.sh
```

Open `http://localhost:3000`, sign in with `DEMO_ACCESS_CODE`, open **Handoff**,
and follow the [five-minute quickstart](docs/quickstart.md).

Pair the plugin:

```sh
export COMMAND_CENTER_URL=http://127.0.0.1:8000
python3 plugins/codex-command-center/scripts/pair.py THE-BROWSER-CODE
python3 plugins/codex-command-center/scripts/health.py
python3 plugins/codex-command-center/scripts/architecture.py lint .
python3 plugins/codex-command-center/scripts/architecture.py sync .
```

`sync` displays the bounded Markdown corpus and asks for confirmation. Session
hooks send hashes only and never upload repository documents.

Then run the generated command in Codex:

```text
/plan Load Command Center handoff <ID> and interview me before editing.
```

Without a connected user-owned OpenAI key, all retrieval, capability, handoff,
and MCP workflows remain usable; Aria and screenshot analysis explicitly mark
local fallback results degraded. Raw screenshots are still validated, hashed,
and discarded. **Connect OpenAI** creates only an encrypted, expiring,
workspace-bound browser-session credential.

## Verify

```sh
pytest
PYTHONPATH=services/memory python3 scripts/eval.py
npm --prefix apps/web run typecheck
npm --prefix apps/web run test
npm --prefix apps/web run build
scripts/security-scan.sh
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/codex-command-center
```

## Documentation

- [Five-minute quickstart](docs/quickstart.md)
- [Complete user manual](docs/user-guide.md)
- [Aria voice and screenshot guide](docs/aria-voice.md)
- [Capability authoring manual](docs/capability-authoring.md)
- [Taste-guided redesign capability](docs/capability-authoring.md#taste-guided-redesign)
- [Handoff lifecycle reference](docs/handoffs.md)
- [Codex plugin installation, migration, and pairing](docs/codex-plugin.md)
- [REST and MCP schemas](docs/api-mcp.md)
- [Architecture and data flow](docs/architecture.md)
- [Full architecture awareness](docs/architecture-awareness.md)
- [Declared retrieval and context compiler](docs/declared-context.md)
- [Evidence graph canvas](docs/graph-canvas.md)
- [PostgreSQL verification under Ubuntu PRoot](docs/postgresql-proot.md)
- [Security, privacy, and approvals](docs/security-privacy.md)
- [Bring your own model key](docs/byok.md)
- [Cloud Run deployment](docs/cloud-run.md)
- [Three-service deployment topology](docs/deployment-topology.md)
- [Current deployment state and continuation receipt](docs/deployment-state.md)
- [Deployment and submission checklist](docs/deployment-checklist.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Reproducible evaluation](docs/eval-report.md)
- [Build Week provenance](docs/build-week-log.md)
- [Three-minute demo script](docs/demo-script.md)
- [Roadmap](docs/roadmap.md)
- [Architecture-awareness implementation plan](docs/plans/full-architecture-awareness.md)
- [Architecture-awareness research lineage](docs/research/full-architecture-awareness-context.md)

The local API publishes OpenAPI at `/openapi.json` and interactive docs at
`/docs`.

## Deployment

The root-level Dockerfile builds the static Next.js client and combined
FastAPI/API/MCP runtime. `cloudbuild.yaml` publishes the image and deploys it to
Cloud Run with `PORT`, Secret Manager bindings, a runtime service account, Cloud
SQL attachment, scale-to-zero, structured Cloud Logging, and bounded instances.
See the [deployment guide](docs/cloud-run.md) before using production data.

Cloud administration and live deployment remain separate, explicitly
authorized operations.

## Provenance and license

Codex Command Center is licensed under
[Apache License 2.0](LICENSE), including its explicit contributor patent grant
and redistribution terms. Attribution is recorded in [NOTICE](NOTICE).
Deployment ideas are adapted from the MIT-licensed
same-author sibling project `Claude-ToolBox-Curriculum`; declared retrieval
components retain their original MIT terms and notices in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Public repository target:
`https://github.com/verbalogicproject-creator/codex-command-center`.
