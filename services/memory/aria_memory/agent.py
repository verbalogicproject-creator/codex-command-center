from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from .architecture import ArchitectureBrief, ArchitectureBriefRequest, ArchitectureCompiler
from .config import Settings
from .context import ContextCompiler
from .db import Database
from .models import ChatRequest, ContextPack, ContextPackRequest, RecallRequest
from .retrieval import Retriever
from .store import AppStore

SYSTEM_PROMPT = """You are Aria, an evidence-backed development memory agent.
Use recall before making factual claims. Cite evidence IDs in square brackets.
Clearly label recorded facts, inferences, and proposals. Surface conflicts and
uncertainty. A proposal is never a saved memory: only a human can confirm it.
Prefer a compact architecture render for cross-project synthesis. Before every
write proposal call check_synthesis. If it reports a conflict, explain the
conflict and do not create a proposal."""


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
          "payload": {
              "type": "object",
              "properties": {
                  "project": {"type": ["string", "null"]},
                  "kind": {"type": ["string", "null"]},
                  "title": {"type": ["string", "null"]},
                  "content": {"type": ["string", "null"]},
                  "reason": {"type": ["string", "null"]},
                  "tags": {"type": ["array", "null"], "items": {"type": "string"}},
                  "target_id": {"type": ["string", "null"]},
              },
              "required": [
                  "project", "kind", "title", "content", "reason", "tags", "target_id"
              ],
              "additionalProperties": False,
          },
          "rationale": {"type": "string"},
          "evidence_ids": {"type": "array", "items": {"type": "string"}}},
         ["operation", "payload", "rationale", "evidence_ids"]),
]


class Aria:
    def __init__(self, settings: Settings, db: Database, store: AppStore,
                 retriever: Retriever, context: ContextCompiler,
                 architecture: ArchitectureCompiler | None = None):
        self.settings, self.db, self.store, self.retriever = settings, db, store, retriever
        self.context = context
        self.architecture = architecture

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
            claim = args["claim"].lower()
            records = self.db.list_memories()
            conflicts = [x.model_dump() for x in records
                if x.kind == "decision" and x.status == "active"
                and "merge" in claim
                and ("not merge" in x.content.lower()
                     or "will not merge" in x.content.lower()
                     or "not as a merged" in x.content.lower())]
            return {"allowed": not conflicts, "conflicts": conflicts[:5]}
        if name == "render_element":
            return {"render": args}
        if name == "propose_memory_write":
            payload = {key: value for key, value in args["payload"].items() if value is not None}
            proposal = self.store.create_proposal(
                session_id, args["operation"], payload,
                args["rationale"], args["evidence_ids"],
            )
            return {"proposal": proposal.model_dump()}
        raise ValueError(f"unknown tool {name}")

    async def run(self, request: ChatRequest) -> list[dict[str, Any]]:
        self.store.add_turn(request.session_id, "user", request.message)
        packet = self.context.build(ContextPackRequest(
            prompt=request.message, token_budget=2_000, memory_limit=8, document_limit=6,
        ))
        repository = str(
            packet.repository_identity.get("repository") or "Command Center"
        )
        architecture_brief = (
            self.architecture.build(ArchitectureBriefRequest(
                repository=repository,
                mode="task",
                prompt=request.message,
                token_budget=1_200,
                document_limit=6,
                section_limit=5,
            ))
            if self.architecture else None
        )
        events: list[dict[str, Any]] = [{"type": "status", "data": {
            "phase": "retrieving", "model": (
                self.settings.aria_deep_model if request.deep_synthesis
                else self.settings.aria_model
            )}}, {"type": "context_pack", "data": packet.model_dump()}]
        if architecture_brief:
            events.append({
                "type": "architecture_brief",
                "data": architecture_brief.model_dump(mode="json"),
            })
        if not self.settings.openai_api_key:
            events.extend(self._fallback(request))
        else:
            try:
                events.extend(await asyncio.to_thread(
                    self._openai_run, request, packet, architecture_brief,
                ))
            except Exception as exc:
                events.append({"type": "status", "data": {
                    "phase": "degraded", "reason": type(exc).__name__}})
                events.extend(self._fallback(request))
        if self._explicit_proposal_request(request.message) and not any(
            event["type"] == "proposal" for event in events
        ):
            answer = next(
                (event["data"]["text"] for event in reversed(events)
                 if event["type"] == "answer"),
                "",
            )
            guard = self.execute_tool("check_synthesis", {
                "project": str(packet.repository_identity.get("repository") or "Command Center"),
                "claim": request.message + " " + answer,
            }, request.session_id)
            if guard["allowed"] and "**Refusal:**" not in answer:
                proposal = self.store.create_proposal(
                    request.session_id,
                    "record_fact",
                    {
                        "project": str(
                            packet.repository_identity.get("repository") or "Command Center"
                        ),
                        "kind": "decision",
                        "title": "Aria decision proposal",
                        "content": answer[:2_000] or request.message[:2_000],
                        "reason": "Explicitly requested by the user for human review",
                        "tags": ["decision", "aria", "proposed"],
                    },
                    "Explicit decision requests always create a persisted pending proposal.",
                    [source.id for source in packet.sources[:8]],
                )
                answer_index = next(
                    (index for index, event in enumerate(events) if event["type"] == "answer"),
                    len(events),
                )
                events.insert(answer_index, {"type": "proposal", "data": proposal.model_dump()})
        answer = next(
            (event["data"]["text"] for event in reversed(events) if event["type"] == "answer"),
            "I could not produce an answer.",
        )
        evidence = [
            hit["id"] for event in events if event["type"] == "evidence"
            for hit in event["data"].get("items", [])
        ]
        evidence.extend(source.id for source in packet.sources)
        evidence = list(dict.fromkeys(evidence))
        self.store.add_turn(request.session_id, "assistant", answer, evidence)
        return events

    @staticmethod
    def _explicit_proposal_request(message: str) -> bool:
        lowered = message.lower()
        action = any(word in lowered for word in (
            "propose", "save", "record", "remember", "create a decision",
        ))
        return action and any(word in lowered for word in (
            "decision", "recommendation", "architecture", "memory",
        ))

    def _fallback(self, request: ChatRequest) -> list[dict[str, Any]]:
        recall = self.retriever.recall(RecallRequest(query=request.message, limit=8))
        hits = recall.hits
        evidence = [{
            "id": hit.memory.id, "title": hit.memory.title,
            "project": hit.memory.project, "score": hit.score,
        } for hit in hits]
        projects = list(dict.fromkeys(hit.memory.project for hit in hits))
        ids = [hit.memory.id for hit in hits]
        if "merge" in request.message.lower():
            guard = self.execute_tool("check_synthesis", {
                "project": "Command Center", "claim": request.message,
            }, request.session_id)
            if not guard["allowed"]:
                conflict_ids = [item["id"] for item in guard["conflicts"]]
                return [
                    {"type": "tool_call", "data": {
                        "name": "check_synthesis", "status": "completed"}},
                    {"type": "evidence", "data": {"items": evidence,
                        "trace": recall.trace.model_dump()}},
                    {"type": "answer", "data": {
                        "text": "**Refusal:** This synthesis conflicts with recorded scope "
                        f"decisions {', '.join(f'[{key}]' for key in conflict_ids)}. "
                        "The projects may contribute evidence through bounded adapters, "
                        "but Aria will not propose merging them.",
                        "degraded": True,
                    }},
                ]
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

    def _openai_run(
        self,
        request: ChatRequest,
        packet: ContextPack,
        architecture_brief: ArchitectureBrief | None = None,
    ) -> list[dict[str, Any]]:
        from openai import OpenAI

        client = OpenAI(api_key=self.settings.openai_api_key)
        history = self.store.recent_turns(request.session_id, 10)
        input_items: list[Any] = [
            {"role": item["role"], "content": item["content"]} for item in history
        ]
        input_items.insert(0, {
            "role": "developer",
            "content": (
                "Use this bounded Command Center context packet as the initial evidence. "
                "Do not claim more than it supports. Architecture evidence is versioned; "
                "preserve its snapshot and source receipts:\n"
                + json.dumps({
                    "context_pack": packet.model_dump(mode="json"),
                    "architecture_brief": (
                        architecture_brief.model_dump(mode="json")
                        if architecture_brief else None
                    ),
                }, separators=(",", ":"))
            ),
        })
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
