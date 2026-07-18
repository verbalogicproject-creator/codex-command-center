#!/usr/bin/env python
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import architecture  # noqa: E402
from client import CommandCenterClient  # noqa: E402

KINDS = {"session_start", "user_prompt_submit", "post_tool_use", "stop"}
TRUTHY = {"1", "true", "yes", "on"}


def read_event() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, dict) else {}


def repository_path(event: dict[str, Any]) -> Path:
    value = event.get("repository") or event.get("cwd") or os.getcwd()
    return Path(str(value)).expanduser()


def repository(event: dict[str, Any]) -> str:
    path = repository_path(event)
    try:
        payload = architecture.inventory(path)
        return str(payload["manifest"]["repository"]["id"])
    except (FileNotFoundError, ValueError):
        return path.name or "unknown"


def _lines(values: list[Any], limit: int = 10) -> str:
    return "; ".join(str(value) for value in values[:limit]) or "none declared"


def render_context(packet: dict[str, Any]) -> str:
    architecture_brief = packet.get("architecture_brief") or (
        packet if packet.get("schema_version") == "command-center-architecture-brief-v1"
        else {}
    )
    durable = packet.get("durable_context") or {}
    identity = architecture_brief.get("repository_identity") or {}
    snapshot = architecture_brief.get("snapshot_receipt") or {}
    health = architecture_brief.get("health_summary") or {}
    lines = [
        "Codex Command Center architecture packet",
        "Boundary: use only this repository-scoped packet; cite evidence IDs; "
        "interview the user before editing.",
        (
            f"Repository: {identity.get('repository') or identity.get('requested') or 'unknown'} "
            f"({identity.get('id') or 'unregistered'})"
        ),
        (
            f"Snapshot: {snapshot.get('snapshot_id') or 'missing'}; "
            f"revision: {snapshot.get('source_revision') or 'unknown'}; "
            f"coverage: {health.get('coverage', 0)}"
        ),
    ]
    local_check = packet.get("local_architecture_check") or {}
    if local_check:
        lines.append(
            "Local check: "
            + (
                "current"
                if not local_check.get("degraded")
                else _lines(local_check.get("degraded_reasons") or [])
            )
        )
    degraded_reasons = list(architecture_brief.get("degraded_reasons") or [])
    if durable.get("degraded"):
        degraded_reasons.append("durable_context_degraded")
    lines.append(
        "Degraded: " + (_lines(list(dict.fromkeys(degraded_reasons))) if degraded_reasons else "no")
    )

    documents = architecture_brief.get("documents") or []
    if documents:
        lines.append("Declared architecture:")
        for item in documents:
            lines.append(
                f"- [{item.get('id')}] {item.get('title')} — {item.get('source_uri')} "
                f"(hash {str(item.get('content_hash') or '')[:12]})"
            )
            if item.get("provides"):
                lines.append(f"  Provides: {_lines(item['provides'])}")
            if item.get("public_interfaces"):
                lines.append(f"  Interfaces: {_lines(item['public_interfaces'])}")
            if item.get("depends_on"):
                lines.append(f"  Depends on: {_lines(item['depends_on'])}")
    sections = architecture_brief.get("sections") or []
    if sections:
        lines.append("Selected architecture sections:")
        for item in sections:
            lines.append(
                f"- [{item.get('id')}] {item.get('source_uri')} — {item.get('heading')}"
            )
            body = str(item.get("body") or "").strip()
            if body:
                lines.append(body)

    lines.append(
        "Safe edit points: "
        + _lines(architecture_brief.get("safe_edit_points") or durable.get("safe_edit_points") or [])
    )
    lines.append(
        "Risk areas: "
        + _lines(architecture_brief.get("risk_areas") or durable.get("risk_areas") or [])
    )
    paths = architecture_brief.get("dependency_paths") or []
    if paths:
        lines.append("Dependency paths: " + "; ".join(" -> ".join(path) for path in paths[:10]))

    durable_records = [
        *(durable.get("facts") or []),
        *(durable.get("episodes") or []),
        *(durable.get("documents") or []),
    ]
    if durable_records:
        lines.append("Durable/project context:")
        for item in durable_records:
            evidence_id = item.get("id")
            title = item.get("title") or item.get("source_uri") or "Untitled"
            content = str(item.get("content") or item.get("body") or "").strip()
            lines.append(f"- [{evidence_id}] {title}")
            if content:
                lines.append(content)

    receipts = [
        *(architecture_brief.get("sources") or []),
        *(durable.get("sources") or []),
    ]
    if receipts:
        lines.append("Evidence receipts:")
        for item in receipts:
            lines.append(
                f"- {item.get('id')}: {_lines(item.get('selection_reasons') or [])}"
            )
    omitted = int(architecture_brief.get("omitted_candidate_count") or 0) + int(
        durable.get("omitted_candidate_count") or 0
    )
    lines.append(f"Omitted lower-ranked candidates: {omitted}")
    return "\n".join(lines)


def context_output(event_name: str, packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": render_context(packet),
        },
    }


def stop_proposals_enabled() -> bool:
    return os.getenv("COMMAND_CENTER_STOP_PROPOSALS", "").lower() in TRUTHY


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in KINDS:
        raise SystemExit("usage: hook.py <session_start|user_prompt_submit|post_tool_use|stop>")
    kind, event = sys.argv[1], read_event()
    client = CommandCenterClient()
    repo = repository(event)
    session_id = str(event.get("session_id") or "") or None
    if kind == "session_start":
        local_check: dict[str, Any]
        try:
            payload = architecture.inventory(repository_path(event))
            local_check = architecture.status(client, payload)
        except FileNotFoundError:
            local_check = {
                "degraded": True,
                "degraded_reasons": ["architecture_manifest_missing"],
            }
        result = {
            "packet_schema": "command-center-session-brief-v1",
            "architecture_brief": client.architecture_brief(
                repo,
                mode="boot",
                prompt=(
                    "Repository briefing: interfaces, safe edit points, "
                    "dependencies, and risks."
                ),
                token_budget=1_200,
            ),
            "local_architecture_check": local_check,
        }
        output = context_output("SessionStart", result)
    elif kind == "user_prompt_submit":
        prompt = str(event.get("prompt") or event.get("message") or "Current coding task")
        result = client.task_pack(prompt, repo, 2_000)
        output = context_output("UserPromptSubmit", result)
    else:
        tool_name = str(event.get("tool_name") or "")[:120] or None
        detail = {
            "summary": (
                str(
                    event.get("summary")
                    or event.get("outcome")
                    or event.get("last_assistant_message")
                    or ""
                )[:2000]
                if kind == "stop"
                else f"{tool_name or 'Codex tool'} completed"
            ),
            "changed_files": list(event.get("changed_files") or [])[:50],
            "duration_ms": event.get("duration_ms"),
            "exit_code": event.get("exit_code"),
            "draft_proposal": kind == "stop" and stop_proposals_enabled(),
        }
        result = client.request("POST", "/api/v1/hooks/events", {
            "kind": kind, "repository": repo, "session_id": session_id,
            "tool_name": tool_name,
            "source_ids": list(event.get("source_ids") or [])[:20],
            "detail": detail,
        })
        if kind == "stop" and result.get("proposal"):
            proposal_id = str(result["proposal"].get("id") or "")
            output = {
                "continue": True,
                "systemMessage": (
                    f"Command Center drafted pending proposal {proposal_id}; "
                    "only the browser can confirm it."
                ),
            }
        else:
            output = {}
    print(json.dumps(output, separators=(",", ":")))


if __name__ == "__main__":
    main()
