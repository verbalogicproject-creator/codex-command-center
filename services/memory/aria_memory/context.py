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


RETRIEVAL_QUERY_LIMIT = 2_000


def bounded_retrieval_query(value: str) -> tuple[str, bool]:
    """Project a long task brief into the bounded retrieval-query contract.

    Context and handoff requests intentionally accept richer prompts than the
    direct recall endpoints. Preserve the full prompt in the caller's durable
    record, while using a deterministic head-and-tail projection for candidate
    retrieval so downstream Pydantic validation cannot reject an otherwise
    valid request.
    """
    normalized = " ".join(value.split())
    if len(normalized) <= RETRIEVAL_QUERY_LIMIT:
        return normalized, False
    marker = " … [bounded retrieval projection] … "
    tail_size = 480
    head_size = RETRIEVAL_QUERY_LIMIT - len(marker) - tail_size
    return normalized[:head_size] + marker + normalized[-tail_size:], True


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
        retrieval_query, query_truncated = bounded_retrieval_query(request.prompt)
        target = request.repository.strip() if request.repository else None
        source_repositories = list(dict.fromkeys(
            item.strip() for item in request.source_repositories if item.strip()
        ))
        cross_sources = [
            item for item in source_repositories
            if not target or item.casefold() != target.casefold()
        ]
        if cross_sources and not target:
            raise ValueError("cross-project context requires a target repository")
        if cross_sources and not request.allow_cross_repository:
            raise ValueError(
                "cross-project context requires explicit allow_cross_repository"
            )
        scopes = list(dict.fromkeys([item for item in [target, *source_repositories] if item]))
        retrieval_scopes: list[str | None] = scopes or [None]
        memory_results = [self.retriever.recall(RecallRequest(
            query=retrieval_query,
            project=repository,
            limit=max(request.memory_limit * 2, 1),
        )) for repository in retrieval_scopes]
        document_results = [self.documents.recall(DocumentRecallRequest(
            query=retrieval_query,
            repository=repository,
            limit=max(request.document_limit * 2, 1),
            mode=request.mode,
        )) for repository in retrieval_scopes]
        memory_rows = [
            {"table": "memories", "id": hit.memory.id, "hit": hit}
            for result in memory_results for hit in result.hits
        ]
        document_rows = [
            {"table": "documents", "id": hit.document.id, "hit": hit}
            for result in document_results for hit in result.hits
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
        selected_ids = list(dict.fromkeys(request.selected_evidence_ids))
        selected_set = set(selected_ids)
        allowed = {item.casefold() for item in scopes}
        for evidence_id in selected_ids:
            memory = self.retriever.db.get_memory(evidence_id)
            document = self.documents.get(evidence_id)
            if not memory and not document:
                raise ValueError(f"selected evidence not found: {evidence_id}")
            repository = memory.project if memory else document.repository
            if allowed and repository.casefold() not in allowed:
                raise ValueError(
                    f"selected evidence is outside the explicit project scope: {evidence_id}"
                )
            if memory:
                if memory.entity_type == "fact" and memory.status == "inactive":
                    raise ValueError(f"selected evidence is inactive: {evidence_id}")
                (episodes if memory.entity_type == "episode" else facts).append(memory)
                accepted_memory += 1
                sources.append(ContextSource(
                    id=memory.id, entity_type="memory", title=memory.title,
                    repository=memory.project, score=1.0,
                    selection_reasons=["explicit_selection"],
                ))
            else:
                documents.append(document)
                accepted_document += 1
                sources.append(ContextSource(
                    id=document.id, entity_type="document", title=document.title,
                    repository=document.repository, score=1.0,
                    selection_reasons=["explicit_selection"],
                ))
        for candidate in fused:
            if candidate["id"] in selected_set:
                continue
            if candidate["table"] == "memories":
                if accepted_memory >= request.memory_limit:
                    continue
                hit = candidate["hit"]
                memory_bucket = episodes if hit.memory.entity_type == "episode" else facts
                memory_bucket.append(hit.memory)
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
        active_repository = target or (repositories[0] if repositories else "unknown")
        identity_document = next(
            (document for document in documents
             if document.repository.lower() == active_repository.lower()),
            documents[0] if documents else None,
        )
        target_documents = [
            document for document in documents
            if document.repository.casefold() == active_repository.casefold()
        ]
        capabilities = list(dict.fromkeys(
            capability for document in target_documents for capability in document.provides
        ))
        safe_edit_points = list(dict.fromkeys(
            point for document in target_documents for point in document.safe_edit_points
        ))
        risk_areas = list(dict.fromkeys(
            risk for document in target_documents for risk in document.risk_areas
        ))
        dependency_paths = [
            [document.id, dependency]
            for document in documents for dependency in document.depends_on
            if dependency
        ]
        total_candidates = sum(
            result.trace.candidates for result in [*memory_results, *document_results]
        )
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
            composition={
                "schema_version": "command-center-context-composition-v1",
                "target_repository": target,
                "source_repositories": source_repositories,
                "selected_evidence_ids": selected_ids,
                "cross_repository": bool(cross_sources),
                "selection_explicit": bool(selected_ids),
                "policy": (
                    "explicit_local_composition" if cross_sources
                    else "repository_scoped"
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
            degraded=any(
                result.trace.degraded for result in [*memory_results, *document_results]
            ),
            routing={
                "packet_schema": "command-center-context-v1",
                "retrieval_mode": request.mode,
                "intent": intent.intent,
                "intent_confidence": intent.confidence,
                "synthesis_model": self.settings.aria_deep_model,
                "dense_model": self.settings.embedding_model,
                "prompt_in_url": False,
                "query_projected": query_truncated,
                "source_prompt_characters": len(request.prompt),
                "retrieval_query_characters": len(retrieval_query),
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
            packet_target = str(
                packet.repository_identity.get("repository") or "unknown"
            ).casefold()
            target_documents = [
                item for item in packet.documents
                if item.repository.casefold() == packet_target
            ]
            packet.declared_capabilities = list(dict.fromkeys(
                value for item in target_documents for value in item.provides
            ))
            packet.safe_edit_points = list(dict.fromkeys(
                value for item in target_documents for value in item.safe_edit_points
            ))
            packet.risk_areas = list(dict.fromkeys(
                value for item in target_documents for value in item.risk_areas
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
            removable = next(
                (index for index in range(len(packet.sources) - 1, -1, -1)
                 if packet.sources[index].id not in selected_set),
                None,
            )
            if removable is None:
                raise ValueError(
                    "token budget is too small for the explicit evidence selection"
                )
            packet.sources.pop(removable)
