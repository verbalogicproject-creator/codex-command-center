from __future__ import annotations

import math
import re
import uuid
from typing import Any

from .health import build_architecture_health
from .models import (
    ArchitectureBrief,
    ArchitectureBriefDocument,
    ArchitectureBriefRequest,
    ArchitectureBriefSection,
    ArchitectureDocumentVersion,
    ArchitectureSourceReceipt,
    ArchitectureStoredSection,
)
from .store import ArchitectureStore

_TERM_RE = re.compile(r"[a-z0-9][a-z0-9._/-]*")
_MAX_SECTION_CHARS = 2_400


def _estimate_tokens(value: str) -> int:
    return max(1, math.ceil(len(value) / 4))


def _terms(value: str) -> set[str]:
    return set(_TERM_RE.findall(value.casefold()))


def _document_surface(document: ArchitectureDocumentVersion) -> str:
    declaration = document.declaration
    fields = [
        document.title,
        document.source_uri,
        str(declaration.get("kind") or ""),
        str(declaration.get("owner_area") or ""),
    ]
    for field in (
        "provides", "public_interfaces", "depends_on", "safe_edit_points",
        "risk_areas", "graph_rag_entities", "main_files",
    ):
        value = declaration.get(field) or []
        fields.extend(str(item) for item in value if item)
    return " ".join(fields).casefold()


def _score_document(
    document: ArchitectureDocumentVersion,
    request: ArchitectureBriefRequest,
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    declaration = document.declaration
    if request.mode == "boot":
        score = 1.0
        if declaration.get("kind") == "architecture_index":
            score += 5
            reasons.append("declared architecture index")
        if document.source_uri.casefold().endswith("readme.md"):
            score += 2
            reasons.append("repository orientation document")
        if declaration.get("status") in {"implemented", "verified", "shipped"}:
            score += 1
            reasons.append("implemented declaration")
        return score, reasons or ["boot orientation"]

    query_terms = _terms(request.prompt)
    surface = _document_surface(document)
    matched = sorted(term for term in query_terms if term in surface)
    score = len(matched) * 2.0
    if request.repository.casefold() in surface:
        score += 0.25
    if matched:
        reasons.append("declared matches: " + ", ".join(matched[:6]))
    if declaration.get("kind") == "architecture_index":
        score += 0.5
        reasons.append("architecture index")
    return score, reasons or ["repository fallback"]


def _score_section(
    section: ArchitectureStoredSection,
    request: ArchitectureBriefRequest,
) -> tuple[float, list[str]]:
    if request.mode == "boot":
        heading = section.heading.casefold()
        score = 2.0 if heading in {"purpose", "overview", "contract"} else 0.25
        return score, [f"boot section: {section.heading}"]
    query_terms = _terms(request.prompt)
    surface = f"{section.heading} {section.body}".casefold()
    matched = sorted(term for term in query_terms if term in surface)
    return (
        len(matched) * 1.5,
        ["section matches: " + ", ".join(matched[:6])] if matched
        else ["parent architecture context"],
    )


def _brief_document(item: ArchitectureDocumentVersion) -> ArchitectureBriefDocument:
    declaration = item.declaration
    return ArchitectureBriefDocument(
        id=item.id,
        stable_id=item.stable_id,
        source_uri=item.source_uri,
        title=item.title,
        kind=str(declaration.get("kind") or "architecture_doc"),
        status=str(declaration.get("status") or "undocumented"),
        owner_area=str(declaration.get("owner_area") or ""),
        audience=list(declaration.get("audience") or []),
        provides=list(declaration.get("provides") or []),
        public_interfaces=list(declaration.get("public_interfaces") or []),
        depends_on=list(declaration.get("depends_on") or []),
        safe_edit_points=list(declaration.get("safe_edit_points") or []),
        risk_areas=list(declaration.get("risk_areas") or []),
        last_verified=item.last_verified,
        content_hash=item.content_hash,
    )


class ArchitectureCompiler:
    def __init__(self, store: ArchitectureStore):
        self.store = store

    @staticmethod
    def _dependency_paths(
        selected_ids: set[str],
        edges: list[Any],
        depth: int = 2,
    ) -> list[list[str]]:
        adjacency: dict[str, list[str]] = {}
        unresolved: list[list[str]] = []
        for edge in edges:
            if edge.relation_type != "DEPENDS_ON":
                continue
            if edge.target_id:
                adjacency.setdefault(edge.source_id, []).append(edge.target_id)
            elif edge.source_id in selected_ids:
                unresolved.append([edge.source_id, edge.target_ref])
        paths: list[list[str]] = []
        frontier = [[source] for source in sorted(selected_ids)]
        for _ in range(depth):
            next_frontier: list[list[str]] = []
            for path in frontier:
                for target in adjacency.get(path[-1], []):
                    if target in path:
                        continue
                    candidate = [*path, target]
                    paths.append(candidate)
                    next_frontier.append(candidate)
            frontier = next_frontier
        return [*paths, *unresolved]

    @staticmethod
    def _recompute(brief: ArchitectureBrief) -> None:
        brief.subsystems = list(dict.fromkeys(
            item.owner_area for item in brief.documents if item.owner_area
        ))
        brief.interfaces = list(dict.fromkeys(
            value for item in brief.documents for value in item.public_interfaces
        ))
        brief.safe_edit_points = list(dict.fromkeys(
            value for item in brief.documents for value in item.safe_edit_points
        ))
        brief.risk_areas = list(dict.fromkeys(
            value for item in brief.documents for value in item.risk_areas
        ))
        brief.token_estimate = 0
        brief.token_estimate = _estimate_tokens(brief.model_dump_json())

    def build(self, request: ArchitectureBriefRequest) -> ArchitectureBrief:
        registered = self.store.resolve_repository(request.repository)
        trace_id = str(uuid.uuid4())
        if registered is None:
            brief = ArchitectureBrief(
                mode=request.mode,
                repository_identity={
                    "requested": request.repository,
                    "status": "unregistered",
                },
                snapshot_receipt={},
                health_summary={"coverage": 0, "degraded": True},
                token_estimate=0,
                token_budget=request.token_budget,
                omitted_candidate_count=0,
                degraded=True,
                degraded_reasons=["repository_unregistered"],
                trace_id=trace_id,
            )
            self._recompute(brief)
            return brief
        snapshot = self.store.active_snapshot(registered.id)
        if snapshot is None:
            brief = ArchitectureBrief(
                mode=request.mode,
                repository_identity={
                    "id": registered.id,
                    "repository": registered.name,
                    "aliases": registered.aliases,
                    "status": "registered",
                },
                snapshot_receipt={},
                health_summary={"coverage": 0, "degraded": True},
                token_estimate=0,
                token_budget=request.token_budget,
                omitted_candidate_count=0,
                degraded=True,
                degraded_reasons=["architecture_snapshot_missing"],
                trace_id=trace_id,
            )
            self._recompute(brief)
            return brief

        health = build_architecture_health(self.store, registered.id)
        document_versions = self.store.list_document_versions(snapshot.id)
        sections = self.store.list_sections(snapshot.id)
        edges = self.store.list_edges(snapshot.id)
        issues = self.store.list_issues(snapshot.id)
        document_scores = [
            (*_score_document(document, request), document)
            for document in document_versions
        ]
        document_scores.sort(
            key=lambda item: (-item[0], item[2].source_uri, item[2].id),
        )
        selected_documents = document_scores[:request.document_limit]
        selected_ids = {item[2].id for item in selected_documents}
        section_scores = [
            (*_score_section(section, request), section)
            for section in sections
            if section.document_version_id in selected_ids
        ]
        section_scores.sort(
            key=lambda item: (-item[0], item[2].stable_id, item[2].id),
        )
        selected_sections = section_scores[:request.section_limit]

        sources: list[ArchitectureSourceReceipt] = []
        for score, reasons, document in selected_documents:
            sources.append(ArchitectureSourceReceipt(
                id=document.id,
                stable_id=document.stable_id,
                entity_type="architecture_document",
                source_uri=document.source_uri,
                evidence_class="declared",
                content_hash=document.content_hash,
                score=score,
                selection_reasons=reasons,
            ))
        document_by_id = {item.id: item for item in document_versions}
        for score, reasons, section in selected_sections:
            parent = document_by_id[section.document_version_id]
            sources.append(ArchitectureSourceReceipt(
                id=section.id,
                stable_id=section.stable_id,
                entity_type="architecture_section",
                source_uri=parent.source_uri,
                section_anchor=section.heading_slug,
                evidence_class="derived",
                content_hash=section.content_hash,
                score=score,
                selection_reasons=reasons,
            ))

        degraded_reasons = list(health.degraded_reasons)
        if sections and health.embedding_coverage < 1:
            degraded_reasons.append("dense_architecture_retrieval_unavailable")
        total_candidates = len(document_scores) + len(section_scores)
        brief = ArchitectureBrief(
            mode=request.mode,
            repository_identity={
                "id": registered.id,
                "repository": registered.name,
                "aliases": registered.aliases,
                "source_revision": snapshot.source_revision,
            },
            snapshot_receipt={
                "snapshot_id": snapshot.id,
                "source_revision": snapshot.source_revision,
                "manifest_hash": snapshot.manifest_hash,
                "corpus_hash": snapshot.corpus_hash,
                "activated_at": snapshot.activated_at,
            },
            health_summary={
                "coverage": health.coverage,
                "valid_cards": health.valid_cards,
                "documents_scanned": health.documents_scanned,
                "missing_card_count": len(health.missing_cards),
                "unresolved_edge_count": len(health.unresolved_edges),
                "ambiguous_edge_count": len(health.ambiguous_edges),
                "embedding_coverage": health.embedding_coverage,
                "degraded": health.degraded,
            },
            documents=[_brief_document(item[2]) for item in selected_documents],
            sections=[
                ArchitectureBriefSection(
                    id=item[2].id,
                    document_version_id=item[2].document_version_id,
                    source_uri=document_by_id[item[2].document_version_id].source_uri,
                    heading=item[2].heading,
                    body=item[2].body[:_MAX_SECTION_CHARS],
                    content_hash=item[2].content_hash,
                )
                for item in selected_sections
            ],
            dependency_paths=self._dependency_paths(selected_ids, edges),
            architecture_issues=[
                {
                    "id": issue.id,
                    "source_uri": issue.source_uri,
                    "code": issue.code,
                    "severity": issue.severity,
                    "detail": issue.detail,
                    "evidence_class": issue.evidence_class,
                }
                for issue in issues[:12]
            ],
            sources=sources,
            token_estimate=0,
            token_budget=request.token_budget,
            omitted_candidate_count=max(total_candidates - len(sources), 0),
            degraded=bool(degraded_reasons),
            degraded_reasons=list(dict.fromkeys(degraded_reasons)),
            trace_id=trace_id,
        )
        self._recompute(brief)
        while brief.token_estimate > request.token_budget and brief.sources:
            removed = brief.sources.pop()
            if removed.entity_type == "architecture_section":
                brief.sections = [
                    item for item in brief.sections if item.id != removed.id
                ]
            else:
                brief.documents = [
                    item for item in brief.documents if item.id != removed.id
                ]
                remaining_document_ids = {
                    item.id for item in brief.documents
                }
                brief.sections = [
                    item for item in brief.sections
                    if item.document_version_id != removed.id
                ]
                brief.sources = [
                    item for item in brief.sources
                    if not (
                        item.entity_type == "architecture_section"
                        and item.source_uri == removed.source_uri
                    )
                ]
                # Dependency paths are derived from the selected document set.
                # Keeping paths whose roots were removed can consume the whole
                # packet budget and evict every actual evidence receipt.
                brief.dependency_paths = [
                    path for path in brief.dependency_paths
                    if path and path[0] in remaining_document_ids
                ]
            brief.omitted_candidate_count += 1
            self._recompute(brief)
        return brief
