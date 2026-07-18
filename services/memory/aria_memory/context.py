from __future__ import annotations

import math
from typing import Any

from declared_core import classify_intent, rrf_fuse

from .config import Settings
from .documents import DeclaredDocumentStore
from .models import (
    ContextPack,
    ContextPackRequest,
    ContextSource,
    DocumentRecallRequest,
    MemoryRecord,
    RecallRequest,
    utc_now,
)
from .retrieval import Retriever


def estimate_tokens(value: str) -> int:
    """Conservative model-independent estimate used only for packet bounding."""
    return max(1, math.ceil(len(value) / 4))


def _memory_text(memory: MemoryRecord) -> str:
    return " ".join((memory.title, memory.content, memory.reason, *memory.tags))


class ContextCompiler:
    """Fuse declared documents and durable memories into one bounded packet."""

    def __init__(
        self,
        settings: Settings,
        retriever: Retriever,
        documents: DeclaredDocumentStore,
    ):
        self.settings = settings
        self.retriever = retriever
        self.documents = documents

    def build(self, request: ContextPackRequest) -> ContextPack:
        memory_result = self.retriever.recall(RecallRequest(
            query=request.prompt,
            project=request.repository,
            limit=max(request.memory_limit * 2, 1),
        ))
        document_result = self.documents.recall(DocumentRecallRequest(
            query=request.prompt,
            repository=request.repository,
            limit=max(request.document_limit * 2, 1),
            mode=request.mode,
        ))
        memory_rows = [
            {"table": "memories", "id": hit.memory.id, "hit": hit}
            for hit in memory_result.hits
        ]
        document_rows = [
            {"table": "documents", "id": hit.document.id, "hit": hit}
            for hit in document_result.hits
        ]
        fused = rrf_fuse(
            [memory_rows, document_rows], weights=[1.0, 1.0],
            labels=["durable-memory", "declared-document"],
        )

        facts: list[MemoryRecord] = []
        episodes: list[MemoryRecord] = []
        documents = []
        sources: list[ContextSource] = []
        accepted_memory = accepted_document = 0
        for candidate in fused:
            if candidate["table"] == "memories":
                if accepted_memory >= request.memory_limit:
                    continue
                hit = candidate["hit"]
                target = episodes if hit.memory.entity_type == "episode" else facts
                target.append(hit.memory)
                accepted_memory += 1
                sources.append(ContextSource(
                    id=hit.memory.id, entity_type="memory", title=hit.memory.title,
                    repository=hit.memory.project, score=float(candidate["rrf_score"]),
                    selection_reasons=hit.provenance,
                    lexical_score=hit.lexical_score, structural_score=hit.structural_score,
                    dense_score=hit.dense_score,
                ))
            else:
                if accepted_document >= request.document_limit:
                    continue
                hit = candidate["hit"]
                documents.append(hit.document)
                accepted_document += 1
                sources.append(ContextSource(
                    id=hit.document.id, entity_type="document", title=hit.document.title,
                    repository=hit.document.repository, score=float(candidate["rrf_score"]),
                    selection_reasons=hit.provenance + hit.structural_paths,
                    lexical_score=hit.lexical_score, structural_score=hit.structural_score,
                    dense_score=hit.dense_score, declared_score=hit.declared_score,
                    dimension_contributions=hit.dimension_contributions,
                ))

        repositories = list(dict.fromkeys(
            [document.repository for document in documents]
            + [memory.project for memory in facts + episodes]
        ))
        active_repository = request.repository or (repositories[0] if repositories else "unknown")
        identity_document = next(
            (document for document in documents
             if document.repository.lower() == active_repository.lower()),
            documents[0] if documents else None,
        )
        capabilities = list(dict.fromkeys(
            capability for document in documents for capability in document.provides
        ))
        safe_edit_points = list(dict.fromkeys(
            point for document in documents for point in document.safe_edit_points
        ))
        risk_areas = list(dict.fromkeys(
            risk for document in documents for risk in document.risk_areas
        ))
        dependency_paths = [
            [document.id, dependency]
            for document in documents for dependency in document.depends_on
            if dependency
        ]
        total_candidates = memory_result.trace.candidates + document_result.trace.candidates
        intent = classify_intent(request.prompt)
        packet = ContextPack(
            repository_identity={
                "repository": active_repository,
                "source_uri": identity_document.source_uri if identity_document else None,
                "kind": identity_document.kind if identity_document else None,
                "status": identity_document.status if identity_document else None,
                "last_verified": (
                    identity_document.last_verified if identity_document else None
                ),
            },
            declared_capabilities=capabilities,
            facts=facts,
            episodes=episodes,
            documents=documents,
            dependency_paths=dependency_paths,
            safe_edit_points=safe_edit_points,
            risk_areas=risk_areas,
            sources=sources,
            token_estimate=0,
            token_budget=request.token_budget,
            omitted_candidate_count=max(total_candidates - len(sources), 0),
            degraded=memory_result.trace.degraded or document_result.trace.degraded,
            routing={
                "packet_schema": "command-center-context-v1",
                "retrieval_mode": request.mode,
                "intent": intent.intent,
                "intent_confidence": intent.confidence,
                "synthesis_model": self.settings.aria_deep_model,
                "dense_model": self.settings.embedding_model,
                "prompt_in_url": False,
                "generated_at": utc_now(),
            },
        )
        # Bound the packet agents actually receive, including provenance and
        # JSON metadata—not only the selected content excerpts.
        while True:
            retained = {source.id for source in packet.sources}
            packet.facts = [item for item in packet.facts if item.id in retained]
            packet.episodes = [item for item in packet.episodes if item.id in retained]
            packet.documents = [item for item in packet.documents if item.id in retained]
            packet.declared_capabilities = list(dict.fromkeys(
                value for item in packet.documents for value in item.provides
            ))
            packet.safe_edit_points = list(dict.fromkeys(
                value for item in packet.documents for value in item.safe_edit_points
            ))
            packet.risk_areas = list(dict.fromkeys(
                value for item in packet.documents for value in item.risk_areas
            ))
            packet.dependency_paths = [
                [item.id, dependency]
                for item in packet.documents for dependency in item.depends_on
                if dependency
            ]
            packet.omitted_candidate_count = max(total_candidates - len(packet.sources), 0)
            packet.token_estimate = 0
            packet.token_estimate = estimate_tokens(packet.model_dump_json())
            packet.token_estimate = estimate_tokens(packet.model_dump_json())
            if packet.token_estimate <= request.token_budget or not packet.sources:
                return packet
            packet.sources.pop()
