from __future__ import annotations

import json
from typing import Any

from .architecture import ArchitectureBriefRequest
from .models import (
    CapabilityRecommendationRequest, ContextPackRequest, HandoffLoadRequest,
    ProposalCreate,
)


TOOL_DEFINITIONS: tuple[tuple[str, str, dict[str, Any], list[str], bool], ...] = (
    ("search_capabilities", "Search trusted provider-neutral capabilities.", {
        "query": {"type": "string"}, "repository": {"type": ["string", "null"]},
        "kind": {"type": ["string", "null"]},
    }, [], False),
    ("recommend_capabilities", "Recommend bounded workflows for a coding task.", {
        "request": {"type": "string"}, "repository": {"type": "string"},
        "screenshot_findings": {"type": "array", "items": {"type": "string"}},
        "limit": {"type": "integer"},
    }, ["request", "repository"], False),
    ("get_capability", "Load one exact capability version.", {
        "capability_id": {"type": "string"}, "version": {"type": ["integer", "null"]},
    }, ["capability_id"], False),
    ("load_handoff", "Load a published handoff and record this client activation.", {
        "handoff_id": {"type": "string"}, "repository": {"type": "string"},
        "client_name": {"type": "string"}, "session_id": {"type": ["string", "null"]},
    }, ["handoff_id", "repository"], False),
    ("build_task_pack", "Build a bounded task pack with a versioned architecture brief.", {
        "prompt": {"type": "string"}, "repository": {"type": ["string", "null"]},
        "token_budget": {"type": "integer"},
    }, ["prompt"], False),
    ("recall_context", "Recall bounded architecture and durable context with provenance.", {
        "query": {"type": "string"}, "repository": {"type": ["string", "null"]},
        "token_budget": {"type": "integer"},
    }, ["query"], False),
    ("get_evidence", "Load one cited memory or declared document.", {
        "source_id": {"type": "string"},
    }, ["source_id"], False),
    ("walk_dependencies", "Walk declared repository and document dependencies.", {
        "source_id": {"type": "string"}, "depth": {"type": "integer"},
    }, ["source_id"], False),
    ("get_timeline", "Get recent durable project evidence.", {
        "project": {"type": ["string", "null"]}, "limit": {"type": "integer"},
    }, [], False),
    ("propose_memory_write", "Draft a pending write; only the browser can confirm it.", {
        "operation": {"type": "string", "enum": [
            "remember_episode", "record_fact", "supersede_fact", "invalidate_fact",
        ]},
        "payload": {"type": "object"}, "rationale": {"type": "string"},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
    }, ["operation", "payload", "rationale"], True),
)


def tool_schema(
    item: tuple[str, str, dict[str, Any], list[str], bool],
) -> dict[str, Any]:
    name, description, properties, required, writes = item
    return {
        "name": name, "description": description,
        "inputSchema": {
            "type": "object", "properties": properties, "required": required,
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": not writes, "destructiveHint": False,
            "idempotentHint": not writes, "openWorldHint": False,
        },
    }


def walk(workspace: Any, source_id: str, depth: int) -> dict[str, Any]:
    if source_id.startswith(("adoc_", "asec_")):
        with workspace.db.connect() as conn:
            if source_id.startswith("adoc_"):
                row = conn.execute(
                    """SELECT snapshot_id FROM architecture_document_versions
                    WHERE id=?""",
                    (source_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """SELECT d.snapshot_id FROM architecture_sections s
                    JOIN architecture_document_versions d
                    ON d.id=s.document_version_id WHERE s.id=?""",
                    (source_id,),
                ).fetchone()
        if not row:
            return {"nodes": [], "edges": [], "paths": []}
        edges = workspace.architecture.list_edges(row["snapshot_id"])
        adjacency: dict[str, list[str]] = {}
        for edge in edges:
            if not edge.target_id:
                continue
            adjacency.setdefault(edge.source_id, []).append(edge.target_id)
            adjacency.setdefault(edge.target_id, []).append(edge.source_id)
        paths = [[source_id]]
        frontier = [[source_id]]
        for _ in range(max(0, min(depth, 5))):
            next_frontier = []
            for path in frontier:
                for target in adjacency.get(path[-1], []):
                    if target not in path:
                        candidate = [*path, target]
                        paths.append(candidate)
                        next_frontier.append(candidate)
            frontier = next_frontier
        node_ids = list(dict.fromkeys(value for path in paths for value in path))
        return {
            "nodes": [{"id": value, "type": "architecture"} for value in node_ids],
            "edges": [
                edge.model_dump(mode="json") for edge in edges
                if edge.source_id in node_ids and edge.target_id in node_ids
            ],
            "paths": paths,
            "snapshot_id": row["snapshot_id"],
        }
    documents = workspace.documents.list()
    nodes = {
        item.id: {"id": item.id, "type": "document", "title": item.title}
        for item in documents
    }
    adjacency: dict[str, list[str]] = {}
    for document in documents:
        for dependency in document.depends_on:
            adjacency.setdefault(document.id, []).append(dependency)
            adjacency.setdefault(dependency, []).append(document.id)
    paths = [[source_id]]
    frontier = [[source_id]]
    for _ in range(max(0, min(depth, 5))):
        next_frontier = []
        for path in frontier:
            for target in adjacency.get(path[-1], []):
                if target not in path:
                    candidate = [*path, target]
                    paths.append(candidate)
                    next_frontier.append(candidate)
        frontier = next_frontier
    ordered = list(dict.fromkeys(key for path in paths for key in path if key in nodes))
    return {"nodes": [nodes[key] for key in ordered], "paths": paths}


def call_tool(workspace: Any, name: str, args: dict[str, Any]) -> Any:
    if name == "search_capabilities":
        return {"items": [
            item.model_dump(mode="json") for item in workspace.toolbox.list_capabilities(
                query=str(args.get("query") or ""), kind=args.get("kind"),
                repository=args.get("repository"),
            )
        ]}
    if name == "recommend_capabilities":
        return workspace.toolbox.recommend(CapabilityRecommendationRequest(
            request=str(args["request"]), repository=str(args["repository"]),
            screenshot_findings=list(args.get("screenshot_findings") or []),
            limit=int(args.get("limit", 3)),
        )).model_dump(mode="json")
    if name == "get_capability":
        item = workspace.toolbox.get_capability(
            str(args["capability_id"]), args.get("version"),
        )
        if not item:
            raise KeyError("capability not found")
        return item.model_dump(mode="json")
    if name == "load_handoff":
        return workspace.toolbox.load_handoff(HandoffLoadRequest(
            handoff_id=str(args["handoff_id"]), repository=str(args["repository"]),
            client_name=str(args.get("client_name") or "Codex"),
            session_id=args.get("session_id"),
        )).model_dump(mode="json")
    if name in {"build_task_pack", "recall_context"}:
        prompt = str(args.get("prompt") or args.get("query") or "")
        repository = args.get("repository")
        token_budget = int(args.get("token_budget", 2_000))
        durable = workspace.context.build(ContextPackRequest(
            prompt=prompt,
            repository=repository,
            token_budget=token_budget,
        ))
        requested_repository = (
            repository
            or durable.repository_identity.get("repository")
            or "unknown"
        )
        architecture = workspace.architecture_compiler.build(
            ArchitectureBriefRequest(
                repository=str(requested_repository),
                mode="task",
                prompt=prompt,
                token_budget=min(token_budget, 2_000),
            )
        )
        return {
            "packet_schema": "command-center-task-pack-v2",
            "architecture_brief": architecture.model_dump(mode="json"),
            "durable_context": durable.model_dump(mode="json"),
            "degraded": architecture.degraded or durable.degraded,
        }
    if name == "get_evidence":
        source_id = str(args["source_id"])
        item = None
        entity_type = None
        if source_id.startswith("adoc_"):
            item = workspace.architecture.get_document_version(source_id)
            entity_type = "architecture_document"
        elif source_id.startswith("asec_"):
            item = workspace.architecture.get_section(source_id)
            entity_type = "architecture_section"
        elif source_id.startswith("aissue_"):
            item = workspace.architecture.get_issue(source_id)
            entity_type = "architecture_issue"
        elif source_id.startswith("aedge_"):
            item = workspace.architecture.get_edge(source_id)
            entity_type = "architecture_edge"
        elif source_id.startswith("doc_"):
            item = workspace.documents.get(source_id)
            entity_type = "document"
        else:
            item = workspace.db.get_memory(source_id)
            entity_type = "memory"
        if not item:
            raise KeyError("evidence not found")
        return {
            "entity_type": entity_type,
            "evidence": item.model_dump(mode="json"),
        }
    if name == "walk_dependencies":
        return walk(workspace, str(args["source_id"]), int(args.get("depth", 2)))
    if name == "get_timeline":
        items = workspace.db.list_memories(args.get("project"))
        items.sort(key=lambda item: item.happened_at, reverse=True)
        return {"items": [
            item.model_dump(mode="json") for item in items[:int(args.get("limit", 20))]
        ]}
    if name == "propose_memory_write":
        body = ProposalCreate(
            operation=args["operation"], payload=args["payload"],
            rationale=args["rationale"], evidence_ids=args.get("evidence_ids", []),
        )
        return workspace.store.create_proposal(
            None, body.operation, body.payload, body.rationale, body.evidence_ids,
        ).model_dump(mode="json")
    raise KeyError(f"unknown tool: {name}")


def handle_rpc(workspace: Any, message: dict[str, Any]) -> dict[str, Any] | None:
    identifier, method = message.get("id"), message.get("method")
    if identifier is None:
        return None
    response: dict[str, Any] = {"jsonrpc": "2.0", "id": identifier}
    try:
        if method == "initialize":
            response["result"] = {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "codex-command-center", "version": "0.5.0"},
                "instructions": (
                    "Load published handoffs before repository edits. Show injected capability "
                    "versions and evidence IDs, then interview the user. Screenshot observations "
                    "are inferences. Memory writes remain pending until browser confirmation."
                ),
            }
        elif method == "tools/list":
            response["result"] = {"tools": [tool_schema(item) for item in TOOL_DEFINITIONS]}
        elif method == "tools/call":
            params = message.get("params") or {}
            result = call_tool(workspace, params["name"], params.get("arguments") or {})
            response["result"] = {"content": [{
                "type": "text", "text": json.dumps(result, indent=2),
            }], "structuredContent": result}
        else:
            response["error"] = {"code": -32601, "message": "Method not found"}
    except PermissionError as exc:
        response["error"] = {"code": -32003, "message": str(exc)}
    except (KeyError, ValueError) as exc:
        response["error"] = {"code": -32004, "message": str(exc)}
    return response
