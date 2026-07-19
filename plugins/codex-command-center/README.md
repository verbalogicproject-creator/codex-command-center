# Codex Command Center plugin

Plan with Aria. Continue in Codex. Bring your toolbox everywhere.

This plugin gives Codex the same versioned ArchitectureBrief and approved,
bounded handoff used by Aria. Run:

```text
/plan Load Command Center handoff <ID> and interview me before editing.
```

Codex loads the exact capability version, approved Open Plan, screenshot
inferences, architecture, evidence receipts, safe edit points, and risks. It does
not expose a confirmation operation: Codex can create a pending proposal, but
only the authenticated Command Center browser can make memory durable.

Start Command Center, select **Pair Codex** in the browser, and set the displayed
one-time value with the pairing helper:

```sh
python3 "${PLUGIN_ROOT}/scripts/pair.py" <CODE> --url https://<host>
python3 "${PLUGIN_ROOT}/scripts/health.py"
python3 "${PLUGIN_ROOT}/scripts/architecture.py" lint .
python3 "${PLUGIN_ROOT}/scripts/architecture.py" sync .
```

The helper joins that browser’s isolated workspace and stores its revocable
workspace token with user-only permissions under `~/.command-center/`. Direct
remote clients may set `COMMAND_CENTER_URL` and `COMMAND_CENTER_TOKEN` instead;
neither value belongs in a repository file.

Version 0.5 recognizes the exact generated command and requires Codex to
visibly call `load_handoff`; the hook never loads it secretly or substitutes
`build_task_pack`. Its health helper checks version compatibility, all ten
tools, authentication, architecture, and handoff availability. It retains
v0.4's explicit `python3` launchers. User-owned OpenAI credentials remain
inside the Command Center browser/API session and never enter this plugin.

The installed plugin defaults to the stdio adapter and honors the caller's
`COMMAND_CENTER_URL`. A direct-HTTP configuration template is provided at
`mcp/remote.example.json`; use one transport at a time.

Architecture sync reads only Markdown paths declared by
`.command-center/architecture.yaml` (or `.json`). `lint` validates without
writing, `status` sends hashes without document bodies, and `sync` prints the
repository, document count, bytes, and revision before asking for explicit
upload confirmation. Session hooks never invoke `sync`. SessionStart performs a
hash-only drift check and loads a boot brief. UserPromptSubmit emits the
visible-load directive for the exact generated command and otherwise loads
task-ranked context.
Unknown repositories remain visibly degraded and never fall back to another
repository's evidence.

The four hooks provide a repository briefing, prompt-specific context, sanitized
tool telemetry, and a pending end-of-session summary. Raw prompt bodies are
never written to hook telemetry. The MCP server exposes:

- `search_capabilities`
- `recommend_capabilities`
- `get_capability`
- `load_handoff`
- `build_task_pack`
- `recall_context`
- `get_evidence`
- `walk_dependencies`
- `get_timeline`
- `propose_memory_write`

See [the complete integration guide](../../docs/codex-plugin.md) for setup,
event payloads, privacy boundaries, and troubleshooting.
