#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import architecture  # noqa: E402
from client import CommandCenterClient  # noqa: E402

PLUGIN_VERSION = "0.5.0"
EXPECTED_TOOLS = {
    "search_capabilities", "recommend_capabilities", "get_capability",
    "load_handoff", "build_task_pack", "recall_context", "get_evidence",
    "walk_dependencies", "get_timeline", "propose_memory_write",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Check service and architecture health.")
    parser.add_argument("repository", nargs="?", default=".")
    args = parser.parse_args()
    client = CommandCenterClient()
    status = client.request("GET", "/api/v1/status")
    initialized = client.request("POST", "/mcp", {
        "jsonrpc": "2.0", "id": "health-init", "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "command-center-health", "version": PLUGIN_VERSION},
        },
    })
    listed = client.request("POST", "/mcp", {
        "jsonrpc": "2.0", "id": "health-tools", "method": "tools/list", "params": {},
    })
    handoffs = client.request("GET", "/api/v1/handoffs")
    server = initialized.get("result", {}).get("serverInfo", {})
    tool_names = {
        item.get("name")
        for item in listed.get("result", {}).get("tools", [])
    }
    compatible = (
        status.get("service_version") == PLUGIN_VERSION
        and server.get("version") == PLUGIN_VERSION
    )
    architecture_status: dict = {
        "degraded": True,
        "degraded_reasons": ["architecture_manifest_missing"],
    }
    try:
        payload = architecture.inventory(Path(args.repository))
        architecture_status = architecture.status(client, payload)
    except FileNotFoundError:
        pass
    print(json.dumps({
        "ok": compatible and tool_names == EXPECTED_TOOLS,
        "service": client.base,
        "authenticated": True,
        "versions": {
            "plugin": PLUGIN_VERSION,
            "api": status.get("service_version"),
            "mcp": server.get("version"),
            "compatible": compatible,
        },
        "mcp_tools": {
            "expected": sorted(EXPECTED_TOOLS),
            "available": sorted(str(item) for item in tool_names),
            "complete": tool_names == EXPECTED_TOOLS,
        },
        "handoffs": {
            "available": len(handoffs.get("items", [])),
            "published": sum(
                item.get("status") == "published"
                for item in handoffs.get("items", [])
            ),
        },
        "memories": status.get("memories", 0),
        "documents": status.get("documents", 0),
        "degraded": status.get("degraded", False),
        "architecture": architecture_status,
    }, indent=2))


if __name__ == "__main__":
    main()
