# Codex Command Center plugin

```yaml
ai_card:
  id: command-center.codex-plugin
  repository: Command Center
  title: Codex Command Center Plugin
  kind: integration_guide
  audience: [user, engineer, ai_agent]
  status: implemented
  owner_area: Codex integration
  main_files: [plugins/codex-command-center, .codex/config.toml]
  public_interfaces: [Codex Command Center v0.4, SessionStart, UserPromptSubmit, "POST /mcp"]
  provides: [plugin installation and pairing, shared architecture hook contract, troubleshooting]
  depends_on: [command-center.architecture-awareness, command-center.api-mcp]
  safe_edit_points: [cache-busted local plugin updates, human-readable receipt rendering]
  risk_areas: [repository-local tokens, unfiltered context fallback, duplicate MCP transports]
  graph_rag_entities: [Codex Command Center, CommandCenterClient, ArchitectureBrief]
  last_verified: 2026-07-19
```

The installable [Codex Command Center plugin](../plugins/codex-command-center)
is the polished client for Aria-to-Codex handoffs. It injects provider-neutral
workflow instructions as bounded session context; it does not claim native
skill installation.

## Contents

- local stdio and direct remote MCP configuration;
- `SessionStart` hash-only drift check and boot ArchitectureBrief;
- `UserPromptSubmit` shared task-specific ArchitectureBrief plus durable
  context;
- sanitized `PostToolUse` telemetry;
- `Stop` telemetry with optional pending proposal drafting;
- token pairing and health helpers;
- ten handoff, capability, context, evidence, timeline, and proposal tools.

## Install and pair

1. Start Command Center or identify the hosted URL.
2. Install `plugins/codex-command-center` using Codex’s local-plugin flow.
3. Select **Pair Codex** in the browser.
4. Run:

   ```sh
   export COMMAND_CENTER_URL=https://<command-center-host>
   python3 plugins/codex-command-center/scripts/pair.py THE-ONE-TIME-CODE
   python3 plugins/codex-command-center/scripts/health.py
   ```

The code expires in five minutes and is consumed once. The server returns a
revocable workspace token; only its hash is stored server-side. The client token
lives under `COMMAND_CENTER_STATE_DIR` or `~/.command-center/` with user-only
permissions. Never place it in a repository, URL, handoff, or log.

## Transport choices

The default `codex-command-center` MCP entry starts the stdio adapter. It reads
the local token file and calls the hosted REST handlers. This is easiest when a
client cannot attach remote headers.

The optional template at
`plugins/codex-command-center/mcp/remote.example.json` calls
`${COMMAND_CENTER_URL}/mcp` and sends `${COMMAND_CENTER_TOKEN}` through
`X-Command-Center-Token`. Both expose the same schemas and result contracts.
Configure either that remote transport or the bundled stdio transport for
ordinary use, not both, to avoid duplicate tool names. The shipped plugin
defaults to stdio and does not override `COMMAND_CENTER_URL`.

Repository development uses `.codex/config.toml` and `.codex/hooks.json`. Their
paths resolve from the Git root, so nested working directories remain safe.
Workspace tokens use `~/.command-center/` by default and never a checkout path.

## Architecture awareness

Version 0.4 discovers `.command-center/architecture.yaml` from nested working
directories. The paired helper exposes:

```sh
python3 plugins/codex-command-center/scripts/architecture.py lint .
python3 plugins/codex-command-center/scripts/architecture.py status .
python3 plugins/codex-command-center/scripts/architecture.py sync .
python3 plugins/codex-command-center/scripts/architecture.py scaffold \
  docs/new-component.md \
  --id command-center.new-component \
  --title "New Component" \
  --repository "Command Center" \
  --owner-area platform
```

The scanner accepts only manifest-selected Markdown and enforces path, symlink,
document-size, corpus-size, and document-count bounds. `status` sends hashes;
`sync` requires confirmation. Hooks never upload document bodies. Unknown
repositories produce `repository_unregistered` and no unfiltered evidence.

## Handoff workflow

Run the exact command emitted by Handoff Builder:

```text
/plan Load Command Center handoff <ID> and interview me before editing.
```

Codex should:

1. visibly call `load_handoff` with the handoff ID and active repository;
2. report the activation receipt;
3. summarize the exact capability ID, version, hash, and provenance;
4. cite injected evidence IDs and selection reasons;
5. label screenshot findings as inferences;
6. state safe edit points, risks, omissions, and degraded state;
7. ask the first interview question before any file edit.

A repository mismatch is a hard failure. Create the handoff for the correct
repository instead of weakening verification.

## MCP tools

| Tool | Purpose |
|---|---|
| `search_capabilities` | Latest trusted workflows, policies, templates, and references |
| `recommend_capabilities` | Primary recommendation and visible alternatives |
| `get_capability` | Exact capability version |
| `load_handoff` | Published, repository-verified packet and activation |
| `build_task_pack` | Bounded ad-hoc task context |
| `recall_context` | Query-specific repository evidence |
| `get_evidence` | One original cited entity |
| `walk_dependencies` | Bounded declared dependency paths |
| `get_timeline` | Recent durable evidence |
| `propose_memory_write` | Pending browser-review proposal |

There is no arbitrary code execution, plugin installation, deployment,
external-action, or memory-confirmation tool.

## Hooks and telemetry

| Hook | Model-visible or stored result |
|---|---|
| `SessionStart` | Hash-only drift check plus bounded boot brief |
| `UserPromptSubmit` | `command-center-task-pack-v2` task brief and durable context |
| `PostToolUse` | Sanitized telemetry only |
| `Stop` | Sanitized completion telemetry; optional pending proposal |

Session and prompt hooks use `hookSpecificOutput.additionalContext`. The
renderer includes repository, snapshot, revision, coverage, versioned source
IDs, selected section bodies, interfaces, dependency paths, safe points, risks,
omissions, and degraded reasons. Telemetry accepts only summary, outcome,
changed files, duration, exit code, and the proposal-draft boolean. Raw prompts
and tool output are dropped.

`COMMAND_CENTER_STOP_PROPOSALS` is off by default because Codex emits Stop after
every turn. When enabled, it still creates only a pending proposal.

## Migration

The former public name was `command-center-memory`. Remove it, install
`codex-command-center`, pair again, and start a new thread. The MCP server name
changes to `codex-command-center`; `build_context_pack` becomes
`build_task_pack`. Version 0.4 standardizes Linux, macOS, and Termux launchers
on `python3`, preventing Codex startup from failing when no optional `python`
alias is installed. It retains v0.3's removal of the old unfiltered context
fallback. Durable workspace data is not deleted. See
[MIGRATION.md](../plugins/codex-command-center/MIGRATION.md).

## Validate and smoke test

```sh
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/codex-command-center

printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' |
python3 plugins/codex-command-center/scripts/mcp_server.py
```

For failures, use the [troubleshooting manual](troubleshooting.md).
