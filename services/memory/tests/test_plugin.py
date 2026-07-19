from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PLUGIN_SCRIPTS = (
    ROOT / "plugins" / "codex-command-center" / "scripts"
)
sys.path.insert(0, str(PLUGIN_SCRIPTS))

from client import CommandCenterClient  # noqa: E402
from hook import context_output, handoff_directive  # noqa: E402
from mcp_server import TOOLS, tool_schema, walk  # noqa: E402
import architecture as plugin_architecture  # noqa: E402
from aria_memory.mcp import TOOL_DEFINITIONS, tool_schema as http_tool_schema  # noqa: E402


def test_context_pack_uses_canonical_task_pack_with_exact_repository(monkeypatch):
    client = CommandCenterClient()
    calls: list[tuple[str, str, dict]] = []

    def request(method, path, body):
        calls.append((method, path, body))
        return {
            "result": {
                "structuredContent": {
                    "packet_schema": "command-center-task-pack-v2",
                    "architecture_brief": {
                        "degraded": True,
                        "degraded_reasons": ["repository_unregistered"],
                    },
                },
            },
        }

    monkeypatch.setattr(client, "request", request)
    packet = client.context_pack("briefing", "unknown-repository", 900)
    assert packet["architecture_brief"]["degraded_reasons"] == [
        "repository_unregistered"
    ]
    assert len(calls) == 1
    method, path, body = calls[0]
    assert (method, path) == ("POST", "/mcp")
    assert body["params"] == {
        "name": "build_task_pack",
        "arguments": {
            "prompt": "briefing",
            "repository": "unknown-repository",
            "token_budget": 900,
        },
    }


def test_dependency_walk_deduplicates_nodes():
    class Client:
        def request(self, _method, _path):
            return {
                "nodes": [
                    {"id": "doc_a"},
                    {"id": "doc_b"},
                    {"id": "project:a"},
                ],
                "edges": [
                    {"source": "project:a", "target": "doc_a"},
                    {"source": "doc_a", "target": "doc_b"},
                ],
            }

    result = walk(Client(), "doc_a", 1)
    assert [node["id"] for node in result["nodes"]] == [
        "doc_a", "project:a", "doc_b",
    ]
    assert result["paths"] == [
        ["doc_a"],
        ["doc_a", "project:a"],
        ["doc_a", "doc_b"],
    ]


def test_only_proposal_tool_is_marked_write_capable():
    schemas = {item["name"]: item for item in map(tool_schema, TOOLS)}
    assert schemas["build_task_pack"]["annotations"]["readOnlyHint"] is True
    assert schemas["get_evidence"]["annotations"]["readOnlyHint"] is True
    assert schemas["propose_memory_write"]["annotations"] == {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }


def test_stdio_and_remote_mcp_tool_schemas_are_identical():
    assert list(map(tool_schema, TOOLS)) == list(
        map(http_tool_schema, TOOL_DEFINITIONS)
    )


def test_context_hooks_use_codex_model_visible_output_shape():
    packet = {
        "packet_schema": "command-center-task-pack-v2",
        "architecture_brief": {
            "repository_identity": {
                "id": "command-center",
                "repository": "Command Center",
            },
            "snapshot_receipt": {
                "snapshot_id": "asnap_test",
                "source_revision": "revision-one",
            },
            "health_summary": {"coverage": 1},
            "documents": [{
                "id": "adoc_test",
                "title": "Architecture Index",
                "source_uri": "docs/architecture.md",
                "content_hash": "a" * 64,
            }],
            "sections": [{
                "id": "asec_test",
                "source_uri": "docs/architecture.md",
                "heading": "Contract",
                "body": "The shared architecture contract.",
            }],
            "safe_edit_points": ["docs and adapters"],
            "risk_areas": ["repository leakage"],
            "sources": [{
                "id": "adoc_test",
                "selection_reasons": ["declared architecture index"],
            }],
            "degraded_reasons": [],
        },
        "durable_context": {
            "facts": [{
                "id": "fact_cc_07",
                "title": "Approval boundary",
                "content": "Only the browser confirms durable memory.",
            }],
            "sources": [{
                "id": "fact_cc_07",
                "selection_reasons": ["task relevance"],
            }],
            "degraded": False,
        },
    }
    output = context_output("SessionStart", packet)
    assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "Codex Command Center architecture packet" in context
    assert "asnap_test" in context
    assert "asec_test" in context
    assert "The shared architecture contract." in context
    assert "fact_cc_07" in context


def test_project_mcp_launcher_bootstraps_from_nested_directory():
    config = tomllib.loads((ROOT / ".codex" / "config.toml").read_text())
    server = config["mcp_servers"]["codex-command-center"]
    request = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "1"},
        },
    })
    process = subprocess.run(
        [server["command"], *server["args"]],
        cwd=ROOT / "services" / "memory",
        env={**os.environ, **server.get("env", {})},
        input=request + "\n",
        text=True,
        capture_output=True,
        timeout=5,
        check=True,
    )
    response = json.loads(process.stdout)
    assert response["result"]["serverInfo"]["name"] == "codex-command-center"
    assert response["result"]["serverInfo"]["version"] == "0.5.0"


def test_plugin_defaults_to_one_stdio_transport_and_home_token_storage():
    plugin = ROOT / "plugins" / "codex-command-center"
    mcp = json.loads((plugin / ".mcp.json").read_text(encoding="utf-8"))
    assert list(mcp["mcpServers"]) == ["codex-command-center"]
    server = mcp["mcpServers"]["codex-command-center"]
    assert server["type"] == "stdio"
    assert server["command"] == "python3"
    assert "env" not in server

    hooks = json.loads((ROOT / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    serialized = json.dumps(hooks)
    assert "COMMAND_CENTER_STATE_DIR" not in serialized
    assert "data/codex-plugin-state" not in serialized

    manifest = json.loads(
        (plugin / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert manifest["version"].split("+", 1)[0] == "0.5.0"
    assert manifest["license"] == "Apache-2.0"

    hook_commands = [
        item["command"]
        for event in json.loads(
            (plugin / "hooks" / "hooks.json").read_text(encoding="utf-8")
        )["hooks"].values()
        for matcher in event
        for item in matcher["hooks"]
    ]
    assert hook_commands
    assert all(command.startswith("python3 ") for command in hook_commands)


def test_exact_handoff_prompt_requires_visible_load_without_secret_fetch():
    prompt = (
        "/plan Load Command Center handoff hoff_abc123 "
        "and interview me before editing."
    )
    directive = handoff_directive(prompt, "command-center", "codex-session")
    assert directive is not None
    assert "`load_handoff`" in directive
    assert '"handoff_id":"hoff_abc123"' in directive
    assert '"repository":"command-center"' in directive
    assert "Do not secretly load" in directive
    assert "`build_task_pack`" in directive
    assert "activation ID" in directive
    assert "role-labelled visual comparison" in directive
    assert "at most three questions" in directive
    assert "Do not edit files" in directive
    assert handoff_directive("Please load hoff_abc123", "command-center", None) is None


def test_architecture_helper_discovers_manifest_from_nested_checkout():
    payload = plugin_architecture.inventory(ROOT / "docs" / "plans")
    assert payload["manifest"]["repository"]["id"] == "command-center"
    assert payload["root"] == ROOT
    assert payload["documents"]
    assert all(item["source_uri"].endswith(".md") for item in payload["documents"])
    assert not any(
        item["source_uri"] == "docs/command-center-atlas.html"
        for item in payload["documents"]
    )


def test_architecture_status_sends_hashes_without_document_bodies():
    payload = plugin_architecture.inventory(ROOT)
    calls: list[tuple[str, str, dict]] = []

    class Client:
        def request(self, method, path, body):
            calls.append((method, path, body))
            return {"snapshot_id": None}

    plugin_architecture.status(Client(), payload)
    method, path, body = calls[0]
    assert (method, path) == ("POST", "/api/v1/architecture/check")
    assert body["documents"]
    assert all(set(item) == {"source_uri", "content_hash"} for item in body["documents"])
    assert all("content" not in item for item in body["documents"])


def test_architecture_sync_sends_only_manifest_selected_markdown():
    payload = plugin_architecture.inventory(ROOT)
    calls: list[dict] = []

    class Client:
        def request(self, _method, _path, body):
            calls.append(body)
            return {"snapshot": {"status": "active"}}

    plugin_architecture.sync(Client(), payload)
    assert calls[0]["documents"] == payload["documents"]
    assert all(item["source_uri"].startswith("docs/") for item in calls[0]["documents"])


def test_architecture_scaffold_is_complete_and_refuses_overwrite(tmp_path):
    path = tmp_path / "docs" / "component.md"
    plugin_architecture.scaffold(
        path,
        card_id="arch.scaffold.component",
        title="Scaffold Component",
        repository="Scaffold Repository",
        owner_area="platform",
    )
    from aria_memory.architecture import parse_architecture_document

    parsed = parse_architecture_document(
        path.read_text(encoding="utf-8"),
        "docs/component.md",
    )
    assert parsed.valid is True
    assert parsed.card.id == "arch.scaffold.component"
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        plugin_architecture.scaffold(
            path,
            card_id="arch.scaffold.component",
            title="Scaffold Component",
            repository="Scaffold Repository",
            owner_area="platform",
        )
