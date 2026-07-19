# Five-minute quickstart

```yaml
ai_card:
  id: command-center.quickstart
  repository: Command Center
  title: Five-Minute Quickstart
  kind: user_guide
  audience: [user, evaluator, ai_agent]
  status: implemented
  owner_area: onboarding
  main_files: [scripts/setup.sh, scripts/dev.sh, plugins/codex-command-center]
  public_interfaces: [Handoff Builder, Pair Codex, Architecture sync]
  provides: [local startup, architecture ingestion, pairing and first handoff]
  depends_on: [command-center.user-guide, command-center.codex-plugin]
  safe_edit_points: [synthetic local demo workflow]
  risk_areas: [skipping architecture sync, putting a token in the repository]
  graph_rag_entities: [Quickstart, Aria, Codex]
  last_verified: 2026-07-18
```

## Run Command Center

Requirements: Python 3.12+, Node 22+, and Git.

```sh
cp .env.example .env
scripts/setup.sh
scripts/dev.sh
```

Open `http://localhost:3000`, enter `DEMO_ACCESS_CODE` (`command-center` by
default), and choose **Handoff** in the bottom dock.

## Prepare a Codex handoff

1. Select the repository.
2. Upload a PNG, JPEG, or WebP screenshot, or paste one into the builder.
3. Describe the change in text or through Aria.
4. Select **Analyze and prepare for Codex**.
5. Review Sol’s explicitly labelled screenshot inferences, the recommended
   workflow and alternatives, the editable Open Plan, included evidence,
   omitted-candidate count, safe edit points, risks, and token estimate.
6. Edit the plan, select **Save Open Plan**, then say or select the exact phrase
   **Approve this handoff**.

Publication exposes only the bounded packet. It does not edit code, install a
tool, deploy, or confirm durable memory. A published handoff is immutable;
changes create a new version.

## Pair Codex

Select **Pair Codex** in the browser and run:

```sh
export COMMAND_CENTER_URL=http://127.0.0.1:8000
python3 plugins/codex-command-center/scripts/pair.py THE-CODE
python3 plugins/codex-command-center/scripts/health.py
```

The one-time code expires in five minutes. The helper exchanges it for a
revocable workspace token and stores that token outside the repository with
user-only filesystem permissions.

Install `plugins/codex-command-center` using Codex’s local plugin flow, or use
the repository-local `.codex/config.toml` and `.codex/hooks.json` while
developing this repository.

## Ingest the repository architecture

From any directory inside the checkout:

```sh
python3 plugins/codex-command-center/scripts/architecture.py lint .
python3 plugins/codex-command-center/scripts/architecture.py status .
python3 plugins/codex-command-center/scripts/architecture.py sync .
```

`lint` is stateless. `status` sends only source paths and hashes. `sync` shows
the exact manifest-selected Markdown corpus and requires explicit confirmation
before uploading document bodies. A successful sync creates an immutable
snapshot shared by Aria and Codex. Session hooks never run `sync`.

## Continue in Codex

Copy the exact command shown by the builder:

```text
/plan Load Command Center handoff <ID> and interview me before editing.
```

The expected first response visibly calls `load_handoff`, names the injected
capability and exact version, cites evidence IDs, distinguishes screenshot
inferences from repository facts, reports the pinned architecture snapshot and
source revision, summarizes safe edit points and risks, and asks the first
interview question before editing.

## Verify

```sh
pytest
npm --prefix apps/web run typecheck
npm --prefix apps/web run test
npm --prefix apps/web run build
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/codex-command-center
```

See the [user manual](user-guide.md), [handoff lifecycle](handoffs.md), and
[plugin guide](codex-plugin.md) for the complete operating model.
