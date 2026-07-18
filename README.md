# Command Center v3

Visual, evidence-backed memory for AI-assisted development.

Command Center gives Aria a durable local workspace, inspectable hybrid recall,
an interactive knowledge graph, and a human approval boundary for every memory
write. The public demo uses 46 synthetic records; no personal memory is shipped.

## What is implemented

- FastAPI + SQLite memory service with isolated workspaces and signed HttpOnly auth.
- Persistent float32 embedding cache keyed by canonical SHA-256 content hashes.
- Lexical, structural and dense retrieval with per-signal scores and degraded fallback.
- OpenAI `text-embedding-3-large` at 256 dimensions, batched in groups of 64.
- GPT-5.6 Responses API loop with seven direct strict function tools, `store: false`,
  bounded visible history, reasoning controls, and stable hashed safety identifiers.
- Durable sessions, pending write proposals, idempotent human confirmation, and
  append-only audit events.
- Responsive static Next.js interface with five real surfaces and a client-laid
  React Flow / Dagre evidence graph.
- One-container Cloud Run packaging, demo quotas, and ephemeral cloud workspaces.

Without an OpenAI key the complete product remains usable: Aria returns a
deterministic evidence-backed synthesis, and retrieval uses the cached local hash
provider. Responses clearly report this as degraded mode.

## Quick start

Requires Python 3.12+ and Node 22+.

```sh
cp .env.example .env
scripts/setup.sh
scripts/dev.sh
```

Open `http://localhost:3000` and use the access code from `DEMO_ACCESS_CODE`
(`command-center` by default). Local SQLite workspaces live permanently under
`data/workspaces/`.

On Termux, `setup.sh` deliberately creates the virtualenv with access to
Termux's native Python packages. This reuses `python-numpy` instead of attempting
an unsupported PyPI source build for Android. If NumPy is not installed, run
`pkg install python-numpy` once and rerun setup.

To use live OpenAI retrieval and Aria:

```sh
export OPENAI_API_KEY=...
export EMBEDDING_PROVIDER=openai
scripts/sync-index.sh
scripts/dev.sh
```

The implementation follows the current official [GPT-5.6 model guide](https://developers.openai.com/api/docs/guides/latest-model),
[tool guide](https://developers.openai.com/api/docs/guides/tools), and
[embeddings guide](https://developers.openai.com/api/docs/guides/embeddings).

## Verify

```sh
pytest
PYTHONPATH=services/memory python scripts/eval.py
npm --prefix apps/web run typecheck
npm --prefix apps/web run test
npm --prefix apps/web run build
scripts/security-scan.sh
```

The production frontend is generated at `apps/web/out`. FastAPI automatically
serves it when present while preserving `/api/v1` route priority.

## API

The OpenAPI schema is available at `/docs` in local development. Key routes:

- `POST /api/v1/auth/demo`
- `GET /api/v1/status`
- `POST /api/v1/recall`
- `GET /api/v1/memories/{table}/{id}`
- `GET /api/v1/graph`
- `GET /api/v1/timeline`
- `GET|POST /api/v1/sessions`
- `POST /api/v1/chat/stream`
- `POST /api/v1/proposals/{id}/confirm`
- `POST /api/v1/proposals/{id}/reject`
- `GET /api/v1/audit`
- `POST /api/v1/index/sync`

See [architecture](docs/architecture.md), [evaluation](docs/eval-report.md), and
the [Build Week log](docs/build-week-log.md).

## Deploy

Create `OPENAI_API_KEY`, `DEMO_ACCESS_CODE`, and `COOKIE_SECRET` secrets in
Google Secret Manager, then submit `cloudbuild.yaml`. The Cloud Run configuration
uses one maximum instance and a 120-second timeout. Authenticated browser
workspaces live under `/tmp`, survive refreshes while the instance lives, and
reset after restart or deployment.

Public repository target: `verbalogicproject-creator/command-center-v3`.

## License

MIT
