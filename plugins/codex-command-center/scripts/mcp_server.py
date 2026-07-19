#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import architecture  # noqa: E402
from client import CommandCenterClient  # noqa: E402

TOOLS = [
    ("search_capabilities", "Search trusted provider-neutral capabilities.", {
        "query": {"type": "string"}, "repository": {"type": ["string", "null"]},
        "kind": {"type": ["string", "null"]},
    }, []),
    ("recommend_capabilities", "Recommend bounded workflows for a coding task.", {
        "request": {"type": "string"}, "repository": {"type": "string"},
        "screenshot_findings": {"type": "array", "items": {"type": "string"}},
        "limit": {"type": "integer"},
    }, ["request", "repository"]),
    ("get_capability", "Load one exact capability version.", {
        "capability_id": {"type": "string"},
        "version": {"type": ["integer", "null"]},
    }, ["capability_id"]),
    ("load_handoff", "Load a published handoff and record this client activation.", {
        "handoff_id": {"type": "string"}, "repository": {"type": "string"},
        "client_name": {"type": "string"},
        "session_id": {"type": ["string", "null"]},
    }, ["handoff_id", "repository"]),
    ("build_task_pack", "Build a bounded task pack with a versioned architecture brief.", {
        "prompt": {"type": "string"}, "repository": {"type": ["string", "null"]},
        "token_budget": {"type": "integer"},
    }, ["prompt"]),
    ("recall_context", "Recall bounded architecture and durable context with provenance.", {
        "query": {"type": "string"}, "repository": {"type": ["string", "null"]},
        "token_budget": {"type": "integer"},
    }, ["query"]),
    ("get_evidence", "Load one cited memory or declared document.", {
        "source_id": {"type": "string"},
    }, ["source_id"]),
    ("walk_dependencies", "Walk declared repository and document dependencies.", {
        "source_id": {"type": "string"}, "depth": {"type": "integer"},
    }, ["source_id"]),
    ("get_timeline", "Get recent durable project evidence.", {
        "project": {"type": ["string", "null"]}, "limit": {"type": "integer"},
    }, []),
    ("propose_memory_write", "Draft a pending write; only the browser can confirm it.", {
        "operation": {"type": "string", "enum": [
            "remember_episode", "record_fact", "supersede_fact", "invalidate_fact"
        ]},
        "payload": {"type": "object"},
        "rationale": {"type": "string"},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
    }, ["operation", "payload", "rationale"]),
]


def tool_schema(item: tuple[str, str, dict[str, Any], list[str]]) -> dict[str, Any]:
    name, description, properties, required = item
    writes = name == "propose_memory_write"
    return {
        "name": name, "description": description,
        "inputSchema": {
            "type": "object", "properties": properties, "required": required,
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": not writes,
            "destructiveHint": False,
            "idempotentHint": not writes,
            "openWorldHint": False,
        },
    }


def walk(client: CommandCenterClient, source_id: str, depth: int) -> Any:
    graph = client.request("GET", "/api/v1/graph")
    nodes = {node["id"]: node for node in graph["nodes"]}
    adjacency: dict[str, list[dict[str, str]]] = {}
    for edge in graph["edges"]:
        adjacency.setdefault(edge["source"], []).append(edge)
        adjacency.setdefault(edge["target"], []).append({
            **edge, "source": edge["target"], "target": edge["source"],
        })
    paths: list[list[str]] = [[source_id]]
    frontier = [[source_id]]
    for _ in range(max(0, min(depth, 5))):
        next_frontier = []
        for path in frontier:
            for edge in adjacency.get(path[-1], []):
                if edge["target"] not in path:
                    candidate = [*path, edge["target"]]
                    paths.append(candidate)
                    next_frontier.append(candidate)
        frontier = next_frontier
    ordered_ids = list(dict.fromkeys(
        key for path in paths for key in path if key in nodes
    ))
    return {"nodes": [nodes[key] for key in ordered_ids], "paths": paths}


def call(client: CommandCenterClient, name: str, args: dict[str, Any]) -> Any:
    if name == "load_handoff":
        repository = str(args.get("repository") or "")
        candidate = Path(repository).expanduser()
        if candidate.is_absolute() or "/" in repository or "\\" in repository:
            try:
                payload = architecture.inventory(candidate)
                args = {
                    **args,
                    "repository": str(payload["manifest"]["repository"]["id"]),
                }
            except (FileNotFoundError, OSError, ValueError):
                pass
    return client.mcp_tool(name, args)


def respond(identifier: Any, result: Any = None, error: Any = None) -> None:
    payload = {"jsonrpc": "2.0", "id": identifier}
    payload["error" if error else "result"] = error or result
    print(json.dumps(payload, separators=(",", ":")), flush=True)


def main() -> None:
    client = CommandCenterClient()
    for line in sys.stdin:
        try:
            message = json.loads(line)
            identifier, method = message.get("id"), message.get("method")
            if method == "initialize":
                respond(identifier, {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "codex-command-center", "version": "0.5.0"},
                    "instructions": (
                        "Load published handoffs before repository edits. Show injected "
                        "capability versions and evidence IDs, then interview the user. "
                        "Screenshot observations and role-labelled visual comparisons "
                        "are inferences. Comparison handoffs permit at most three "
                        "focused questions. Use the repository identity supplied by the "
                        "handoff directive or local architecture manifest, never a "
                        "filesystem path. Memory writes remain pending until browser "
                        "confirmation."
                    ),
                })
            elif method == "tools/list":
                respond(identifier, {"tools": [tool_schema(item) for item in TOOLS]})
            elif method == "tools/call":
                params = message.get("params", {})
                result = call(client, params["name"], params.get("arguments", {}))
                respond(identifier, {"content": [{
                    "type": "text", "text": json.dumps(result, indent=2),
                }], "structuredContent": result})
            elif identifier is not None:
                respond(identifier, error={"code": -32601, "message": "Method not found"})
        except Exception as error:
            if "identifier" in locals() and identifier is not None:
                respond(identifier, error={"code": -32000, "message": str(error)})


if __name__ == "__main__":
    main()
