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

## Run everything locally

Requirements: Python 3.12+, Node 22+, and Git.

```sh
git clone https://github.com/verbalogicproject-creator/codex-command-center.git
cd codex-command-center
cp .env.example .env
scripts/setup.sh
scripts/dev.sh
```

This starts FastAPI at `http://127.0.0.1:8000` and Next.js at
`http://localhost:3000`. Open the web URL, enter `DEMO_ACCESS_CODE`
(`command-center` by default), and choose **Handoff** in the bottom dock.
Local mode uses one workspace-isolated SQLite database under the gitignored
`data/` directory. Stop both processes with `Ctrl-C`.

The bundled Codex MCP adapter also runs locally as a stdio process, but it calls
the same API handlers at port 8000:

```sh
export COMMAND_CENTER_URL=http://127.0.0.1:8000
python3 plugins/codex-command-center/scripts/pair.py THE-BROWSER-CODE
python3 plugins/codex-command-center/scripts/health.py
```

Select **Pair Codex** in the browser to obtain `THE-BROWSER-CODE`.
Use the dialog's **Copy terminal command** action and paste it into the shell,
not into the Codex prompt. The pairing code is consumed once and is not part of
the generated `/plan Load Command Center handoff ...` command.
Start Codex from the repository root or a nested directory. The checked-in
`.codex/config.toml` starts the stdio adapter and the hooks inherit
`COMMAND_CENTER_URL`; when the variable is unset they default to the local API.
Starting Codex before pairing is supported: hooks report an expected unpaired
state without failing, and the running stdio adapter discovers the token after
the terminal pairing command completes.

## Use hosted Command Center and hosted MCP

No local web or API process is required for the deployed workspace. Open:

```text
https://command-center-web-67134152472.me-west1.run.app
```

Enter the demo access code supplied with the deployment, select **Pair Codex**,
and pair the plugin with the hosted origin:

```sh
export COMMAND_CENTER_URL=https://command-center-web-67134152472.me-west1.run.app
python3 plugins/codex-command-center/scripts/pair.py THE-BROWSER-CODE
python3 plugins/codex-command-center/scripts/health.py
```

The recommended Codex transport remains the plugin's stdio bridge: the process
runs on your machine, reads the revocable token from
`~/.command-center/codex-workspace-token`, and calls the hosted Command Center
and MCP handlers. Launch Codex from the same shell so hooks inherit
`COMMAND_CENTER_URL`.

Clients that can attach an HTTP header may instead call the stateless hosted
MCP endpoint directly:

```text
POST https://command-center-mcp-67134152472.me-west1.run.app/mcp
X-Command-Center-Token: <workspace token>
```

The template is
`plugins/codex-command-center/mcp/remote.example.json`. Configure either the
stdio bridge or direct HTTP, not both, or the client will see duplicate tools.
The browser credential used for optional Sol/Luna/Realtime features is separate
from the revocable MCP workspace token.

## Prepare a Codex handoff

1. Select the repository.
2. Name the target surface.
3. Upload or paste the **current product** screenshot.
4. Upload or paste the **reference direction** screenshot.
5. Describe the desired merge in text or through Aria.
6. Select **Compare and prepare for Codex**.
7. Review Sol’s role-labelled findings and the visible `preserve`, `adopt`,
   `avoid`, `conflicts`, and `unresolved` groups, followed by the recommended
   workflow, editable Open Plan, evidence, safe edit points, risks, and token
   estimate.
8. Edit the plan, select **Save Open Plan**, then say or select the exact phrase
   **Approve this handoff**.

Publication exposes only the bounded packet. It does not edit code, install a
tool, deploy, or confirm durable memory. A published handoff is immutable;
changes create a new version.

## Pair Codex

For either local or hosted mode, select **Pair Codex** in the corresponding
browser and run:

```sh
export COMMAND_CENTER_URL=http://127.0.0.1:8000
python3 plugins/codex-command-center/scripts/pair.py THE-CODE
python3 plugins/codex-command-center/scripts/health.py
```

The one-time code expires in five minutes. The helper exchanges it for a
revocable workspace token and stores that token outside the repository with
user-only filesystem permissions. Run this command in the terminal only; never
append the pairing code to a Codex prompt or handoff command.

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
and role-labelled comparison inferences from repository facts, reports the
pinned architecture snapshot and source revision, summarizes safe edit points
and risks, and asks at most three focused comparison questions before presenting
an implementation plan. Code edits still wait for explicit plan approval.

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
