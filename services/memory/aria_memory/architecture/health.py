from __future__ import annotations

from typing import Iterable

from .models import ArchitectureHashEntry, ArchitectureHealth
from .store import ArchitectureStore


def build_architecture_health(
    store: ArchitectureStore,
    repository: str,
    *,
    local_documents: Iterable[ArchitectureHashEntry] = (),
    local_revision: str = "",
    manifest_hash: str | None = None,
    snapshot_id: str | None = None,
) -> ArchitectureHealth:
    registered = store.resolve_repository(repository)
    if registered is None:
        return ArchitectureHealth(
            repository=repository,
            degraded=True,
            degraded_reasons=["repository_unregistered"],
        )
    snapshot = (
        store.get_snapshot(snapshot_id)
        if snapshot_id else store.active_snapshot(registered.id)
    )
    if snapshot is not None and snapshot.repository_id != registered.id:
        snapshot = None
    if snapshot is None:
        return ArchitectureHealth(
            repository_id=registered.id,
            repository=registered.name,
            aliases=registered.aliases,
            degraded=True,
            degraded_reasons=["architecture_snapshot_missing"],
        )

    issues = store.list_issues(snapshot.id)
    edges = store.list_edges(snapshot.id)
    document_versions = store.list_document_versions(snapshot.id)
    missing_cards = sorted({
        issue.source_uri for issue in issues if issue.code == "missing_ai_card"
    })
    invalid_cards = [
        {
            "source_uri": issue.source_uri,
            "code": issue.code,
            "detail": issue.detail,
        }
        for issue in issues
        if issue.severity == "error"
    ]
    conflicts = [
        {
            "source_uri": issue.source_uri,
            "code": issue.code,
            "detail": issue.detail,
        }
        for issue in issues
        if issue.code in {
            "conflicting_declarations",
            "duplicate_stable_id",
            "duplicate_source_uri",
            "repository_mismatch",
        }
    ]
    unresolved_edges = [
        {
            "id": edge.id,
            "source_id": edge.source_id,
            "target_ref": edge.target_ref,
            "relation_type": edge.relation_type,
            "source_field": edge.source_field,
        }
        for edge in edges if edge.resolution_status == "unresolved"
    ]
    ambiguous_edges = [
        {
            "id": edge.id,
            "source_id": edge.source_id,
            "target_ref": edge.target_ref,
            "relation_type": edge.relation_type,
            "source_field": edge.source_field,
        }
        for edge in edges if edge.resolution_status == "ambiguous"
    ]

    local_by_uri = {
        item.source_uri: item.content_hash for item in local_documents
    }
    active_by_uri = {
        item.source_uri: item.content_hash for item in document_versions
    }
    stale_sources: list[dict[str, str]] = []
    if local_by_uri:
        for source_uri, active_hash in active_by_uri.items():
            local_hash = local_by_uri.get(source_uri)
            if local_hash is None:
                stale_sources.append({
                    "source_uri": source_uri,
                    "reason": "missing_from_local_inventory",
                    "snapshot_hash": active_hash,
                })
            elif local_hash != active_hash:
                stale_sources.append({
                    "source_uri": source_uri,
                    "reason": "content_hash_changed",
                    "snapshot_hash": active_hash,
                    "local_hash": local_hash,
                })
        for source_uri, local_hash in local_by_uri.items():
            if source_uri not in active_by_uri and source_uri not in missing_cards:
                stale_sources.append({
                    "source_uri": source_uri,
                    "reason": "not_in_active_snapshot",
                    "local_hash": local_hash,
                })

    with store.db.connect() as conn:
        section_count = int(conn.execute(
            """SELECT COUNT(*) FROM architecture_sections s
            JOIN architecture_document_versions d ON d.id=s.document_version_id
            WHERE d.snapshot_id=?""",
            (snapshot.id,),
        ).fetchone()[0])
        embedding_count = int(conn.execute(
            """SELECT COUNT(*) FROM architecture_section_embeddings e
            JOIN architecture_sections s ON s.id=e.section_id
            JOIN architecture_document_versions d ON d.id=s.document_version_id
            WHERE d.snapshot_id=?""",
            (snapshot.id,),
        ).fetchone()[0])
    embedding_coverage = (
        embedding_count / section_count if section_count else 0
    )

    degraded_reasons: list[str] = []
    if missing_cards:
        degraded_reasons.append("architecture_card_gaps")
    if invalid_cards:
        degraded_reasons.append("invalid_architecture_cards")
    if conflicts:
        degraded_reasons.append("architecture_conflicts")
    if stale_sources:
        degraded_reasons.append("local_snapshot_drift")
    if unresolved_edges:
        degraded_reasons.append("unresolved_architecture_edges")
    if ambiguous_edges:
        degraded_reasons.append("ambiguous_architecture_edges")
    if local_revision and local_revision != snapshot.source_revision:
        degraded_reasons.append("source_revision_mismatch")
    if manifest_hash and manifest_hash != snapshot.manifest_hash:
        degraded_reasons.append("manifest_hash_mismatch")

    return ArchitectureHealth(
        repository_id=registered.id,
        repository=registered.name,
        aliases=registered.aliases,
        snapshot_id=snapshot.id,
        snapshot_status=snapshot.status,
        source_revision=snapshot.source_revision,
        last_sync=snapshot.activated_at,
        documents_scanned=snapshot.document_count,
        valid_cards=snapshot.valid_count,
        coverage=(
            snapshot.valid_count / snapshot.document_count
            if snapshot.document_count else 0
        ),
        missing_cards=missing_cards,
        invalid_cards=invalid_cards,
        conflicts=conflicts,
        stale_sources=stale_sources,
        unresolved_edges=unresolved_edges,
        ambiguous_edges=ambiguous_edges,
        embedding_coverage=embedding_coverage,
        degraded=bool(degraded_reasons),
        degraded_reasons=list(dict.fromkeys(degraded_reasons)),
    )
