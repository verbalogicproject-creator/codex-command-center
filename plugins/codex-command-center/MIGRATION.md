# Migrating from command-center-memory

The public plugin is now **Codex Command Center** (`codex-command-center`).
Remove the old plugin entry, install this directory, and pair again so the
server can issue a revocable workspace token. Existing durable memories remain
in the workspace; old cookie files are not migrated because the new transport
stores only a workspace token.

The MCP server name changes from `command-center-memory` to
`codex-command-center`. The old `build_context_pack` tool is now
`build_task_pack`; the remaining memory and evidence tools keep their semantics.
New handoff tools are `search_capabilities`, `recommend_capabilities`,
`get_capability`, and `load_handoff`.

Version 0.3 adds the shared `command-center-architecture-brief-v1` contract.
SessionStart now checks local hashes without uploading documents and injects a
boot brief. UserPromptSubmit uses `command-center-task-pack-v2`. The previous
unfiltered context fallback was removed: a checkout must match a registered
repository name, ID, or declared alias.
