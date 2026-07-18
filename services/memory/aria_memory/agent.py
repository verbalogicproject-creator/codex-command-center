from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from .config import Settings
from .db import Database
from .models import ChatRequest, RecallRequest
from .retrieval import Retriever
from .store import AppStore

SYSTEM_PROMPT = """You are Aria, an evidence-backed development memory agent.
Use recall before making factual claims. Cite evidence IDs in square brackets.
Clearly label recorded facts, inferences, and proposals. Surface conflicts and
uncertainty. A proposal is never a saved memory: only a human can confirm it.
Prefer a compact architecture render for cross-project synthesis."""


def tool(name: str, description: str, properties: dict[str, Any],
         required: list[str]) -> dict[str, Any]:
    return {
        "type": "function", "name": name, "description": description,
        "parameters": {
            "type": "object", "properties": properties, "required": required,
            "additionalProperties": False,
        },
        "strict": True,
    }


TOOLS = [
    tool("recall_memories", "Retrieve ranked memory evidence.",
         {"query": {"type": "string"}, "limit": {"type": "integer"}}, ["query", "limit"]),
    tool("get_memory", "Get one full evidence record.",
         {"memory_id": {"type": "string"}}, ["memory_id"]),
    tool("walk_memory_graph", "Get semantic neighbors for evidence IDs.",
         {"memory_ids": {"type": "array", "items": {"type": "string"}}}, ["memory_ids"]),
    tool("get_timeline", "Get recent evidence for a project.",
         {"project": {"type": ["string", "null"]}, "limit": {"type": "integer"}},
         ["project", "limit"]),
    tool("check_synthesis", "Check a proposed decision for conflicting active evidence.",
         {"project": {"type": "string"}, "claim": {"type": "string"}}, ["project", "claim"]),
    tool("render_element", "Render an inspectable architecture or evidence block.",
         {"title": {"type": "string"}, "kind": {"type": "string"},
          "summary": {"type": "string"},
          "evidence_ids": {"type": "array", "items": {"type": "string"}}},
         ["title", "kind", "summary", "evidence_ids"]),
    tool("propose_memory_write", "Create a pending write for human confirmation.",
         {"operation": {"type": "string", "enum": [
             "remember_episode", "record_fact", "supersede_fact", "invalidate_fact"]},
          "payload": {"type": "object", "additionalProperties": True},
          "rationale": {"type": "string"},
          "evidence_ids": {"type": "array", "items": {"type": "string"}}},
         ["operation", "payload", "rationale", "evidence_ids"]),
]


class Aria:
    def __init__(self, settings: Settings, db: Database, store: AppStore,
                 retriever: Retriever):
        self.settings, self.db, self.store, self.retriever = settings, db, store, retriever

    def execute_tool(self, name: str, args: dict[str, Any],
                     session_id: str) -> dict[str, Any]:
        if name == "recall_memories":
            result = self.retriever.recall(RecallRequest(
                query=args["query"], limit=min(args["limit"], 12)
            ))
            return result.model_dump()
        if name == "get_memory":
            memory = self.db.get_memory(args["memory_id"])
            return {"memory": memory.model_dump() if memory else None}
        if name == "walk_memory_graph":
            wanted = set(args["memory_ids"])
            records = self.db.list_memories()
            projects = {x.project for x in records if x.id in wanted}
            neighbors = [x.model_dump() for x in records if x.project in projects][:30]
            return {"neighbors": neighbors}
        if name == "get_timeline":
            records = self.db.list_memories(args["project"])
            records.sort(key=lambda x: x.happened_at, reverse=True)
            return {"items": [x.model_dump() for x in records[:args["limit"]]]}
        if name == "check_synthesis":
            conflicts = [
                x.model_dump() for x in self.db.list_memories(args["project"])
                if x.kind == "decision" and x.status == "active"
                and args["claim"].lower() not in x.content.lower()
            ]
            return {"allowed": not conflicts, "conflicts": conflicts[:5]}
        if name == "render_element":
            return {"render": args}
        if name == "propose_memory_write":
            proposal = self.store.create_proposal(
                session_id, args["operation"], args["payload"],
                args["rationale"], args["evidence_ids"],
            )
            return {"proposal": proposal.model_dump()}
        raise ValueError(f"unknown tool {name}")

    async def run(self, request: ChatRequest) -> list[dict[str, Any]]:
        self.store.add_turn(request.session_id, "user", request.message)
        events: list[dict[str, Any]] = [{"type": "status", "data": {
            "phase": "retrieving", "model": (
                self.settings.aria_deep_model if request.deep_synthesis
                else self.settings.aria_model
            )}}]
        if not self.settings.openai_api_key:
            events.extend(self._fallback(request))
        else:
            try:
                events.extend(await asyncio.to_thread(self._openai_run, request))
            except Exception as exc:
                events.append({"type": "status", "data": {
                    "phase": "degraded", "reason": type(exc).__name__}})
                events.extend(self._fallback(request))
        answer = next(
            (event["data"]["text"] for event in reversed(events) if event["type"] == "answer"),
            "I could not produce an answer.",
        )
        evidence = [
            hit["id"] for event in events if event["type"] == "evidence"
            for hit in event["data"].get("items", [])
        ]
        self.store.add_turn(request.session_id, "assistant", answer, evidence)
        return events

    def _fallback(self, request: ChatRequest) -> list[dict[str, Any]]:
        recall = self.retriever.recall(RecallRequest(query=request.message, limit=8))
        hits = recall.hits
        evidence = [{
            "id": hit.memory.id, "title": hit.memory.title,
            "project": hit.memory.project, "score": hit.score,
        } for hit in hits]
        projects = list(dict.fromkeys(hit.memory.project for hit in hits))
        ids = [hit.memory.id for hit in hits]
        summary = (
            "A private mobile assistant can use Project Memory as the durable evidence layer, "
            "Hexagon as the future device inference adapter, and Command Center as the visual "
            "control surface. LifeOS and ADHD-SOS remain bounded evidence sources."
        )
        citations = " ".join(f"[{item}]" for item in ids[:5])
        events = [
            {"type": "tool_call", "data": {"name": "recall_memories", "status": "completed"}},
            {"type": "evidence", "data": {"items": evidence, "trace": recall.trace.model_dump()}},
            {"type": "render", "data": {"kind": "architecture", "title": "Private mobile stack",
                "summary": summary, "projects": projects, "evidence_ids": ids}},
        ]
        if any(word in request.message.lower() for word in ("propose", "decision", "recommend")):
            proposal = self.store.create_proposal(
                request.session_id, "record_fact",
                {"project": "Command Center", "kind": "decision",
                 "title": "Private mobile assistant architecture", "content": summary,
                 "reason": "Evidence-backed cross-project synthesis",
                 "tags": ["mobile", "private", "architecture"]},
                "Save the synthesis as a reviewed decision.", ids[:5],
            )
            events.append({"type": "proposal", "data": proposal.model_dump()})
        events.append({"type": "answer", "data": {
            "text": f"**Inference:** {summary}\n\nEvidence: {citations}",
            "degraded": True,
        }})
        return events

    def _openai_run(self, request: ChatRequest) -> list[dict[str, Any]]:
        from openai import OpenAI

        client = OpenAI(api_key=self.settings.openai_api_key)
        history = self.store.recent_turns(request.session_id, 10)
        input_items: list[Any] = [
            {"role": item["role"], "content": item["content"]} for item in history
        ]
        events: list[dict[str, Any]] = []
        model = self.settings.aria_deep_model if request.deep_synthesis else self.settings.aria_model
        safety_id = hashlib.sha256(f"cc3:{request.session_id}".encode()).hexdigest()
        for _ in range(6):
            response = client.responses.create(
                model=model, instructions=SYSTEM_PROMPT, input=input_items,
                tools=TOOLS, store=False, parallel_tool_calls=False,
                safety_identifier=safety_id,
                reasoning={"effort": "high" if request.deep_synthesis else "low"},
            )
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                text = response.output_text.strip()
                events.append({"type": "answer", "data": {"text": text, "degraded": False}})
                return events
            input_items.extend(response.output)
            for call in calls:
                args = json.loads(call.arguments)
                events.append({"type": "tool_call", "data": {
                    "name": call.name, "arguments": args, "status": "running"}})
                result = self.execute_tool(call.name, args, request.session_id)
                if call.name == "recall_memories":
                    events.append({"type": "evidence", "data": {
                        "items": [{
                            "id": hit["memory"]["id"], "title": hit["memory"]["title"],
                            "project": hit["memory"]["project"], "score": hit["score"],
                        } for hit in result["hits"]],
                        "trace": result["trace"],
                    }})
                elif call.name == "render_element":
                    events.append({"type": "render", "data": result["render"]})
                elif call.name == "propose_memory_write":
                    events.append({"type": "proposal", "data": result["proposal"]})
                input_items.append({
                    "type": "function_call_output", "call_id": call.call_id,
                    "output": json.dumps(result),
                })
        raise RuntimeError("tool loop exceeded")
