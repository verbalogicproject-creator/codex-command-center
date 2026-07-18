from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any, Iterable

from ..db import Database
from ..models import utc_now
from .models import (
    ArchitectureDocumentVersion,
    ArchitectureEdge,
    ArchitectureIssue,
    ArchitectureParseResult,
    ArchitectureRepository,
    ArchitectureSnapshot,
    ArchitectureStoredIssue,
    ArchitectureStoredSection,
)

_RELATION_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
_REPOSITORY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")


def _digest(*values: str, length: int = 24) -> str:
    surface = "\x1f".join(values)
    return hashlib.sha256(surface.encode("utf-8")).hexdigest()[:length]


def _corpus_hash(documents: Iterable[ArchitectureParseResult]) -> str:
    entries = sorted(
        (document.source_uri, document.content_hash) for document in documents
    )
    surface = json.dumps(entries, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(surface.encode("utf-8")).hexdigest()


def _entity_id(kind: str, value: str) -> str:
    return f"{kind}:{_digest(value, length=20)}"


class ArchitectureStore:
    """Transactional versioned architecture snapshots over the workspace DB."""

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _snapshot_from_row(row: Any) -> ArchitectureSnapshot:
        return ArchitectureSnapshot(**dict(row))

    @staticmethod
    def _repository_from_row(row: Any) -> ArchitectureRepository:
        values = dict(row)
        values["aliases"] = json.loads(values.pop("aliases_json"))
        return ArchitectureRepository(**values)

    @staticmethod
    def _document_from_row(row: Any) -> ArchitectureDocumentVersion:
        values = dict(row)
        values["declaration"] = json.loads(values.pop("declaration_json"))
        return ArchitectureDocumentVersion(**values)

    @staticmethod
    def _section_from_row(row: Any) -> ArchitectureStoredSection:
        return ArchitectureStoredSection(**dict(row))

    @staticmethod
    def _edge_from_row(row: Any) -> ArchitectureEdge:
        return ArchitectureEdge(**dict(row))

    @staticmethod
    def _issue_from_row(row: Any) -> ArchitectureStoredIssue:
        values = dict(row)
        values["detail"] = json.loads(values.pop("detail_json"))
        return ArchitectureStoredIssue(**values)

    def get_snapshot(self, snapshot_id: str) -> ArchitectureSnapshot | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM architecture_snapshots WHERE id=?",
                (snapshot_id,),
            ).fetchone()
        return self._snapshot_from_row(row) if row else None

    def list_repositories(self) -> list[ArchitectureRepository]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM architecture_repositories ORDER BY name,id"
            ).fetchall()
        return [self._repository_from_row(row) for row in rows]

    def resolve_repository(self, value: str) -> ArchitectureRepository | None:
        wanted = value.strip().casefold()
        for repository in self.list_repositories():
            candidates = [repository.id, repository.name, *repository.aliases]
            if wanted in {candidate.casefold() for candidate in candidates}:
                return repository
        return None

    def active_snapshot(self, repository: str) -> ArchitectureSnapshot | None:
        registered = self.resolve_repository(repository)
        if registered is None:
            return None
        with self.db.connect() as conn:
            row = conn.execute(
                """SELECT * FROM architecture_snapshots
                WHERE repository_id=? AND status='active'""",
                (registered.id,),
            ).fetchone()
        return self._snapshot_from_row(row) if row else None

    def list_snapshots(self, repository: str) -> list[ArchitectureSnapshot]:
        registered = self.resolve_repository(repository)
        if registered is None:
            return []
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT * FROM architecture_snapshots
                WHERE repository_id=? ORDER BY created_at,id""",
                (registered.id,),
            ).fetchall()
        return [self._snapshot_from_row(row) for row in rows]

    def get_document_version(
        self, document_version_id: str,
    ) -> ArchitectureDocumentVersion | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM architecture_document_versions WHERE id=?",
                (document_version_id,),
            ).fetchone()
        return self._document_from_row(row) if row else None

    def list_document_versions(
        self, snapshot_id: str,
    ) -> list[ArchitectureDocumentVersion]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT * FROM architecture_document_versions
                WHERE snapshot_id=? ORDER BY source_uri""",
                (snapshot_id,),
            ).fetchall()
        return [self._document_from_row(row) for row in rows]

    def list_sections(self, snapshot_id: str) -> list[ArchitectureStoredSection]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT s.* FROM architecture_sections s
                JOIN architecture_document_versions d ON d.id=s.document_version_id
                WHERE d.snapshot_id=? ORDER BY d.source_uri,s.ordinal""",
                (snapshot_id,),
            ).fetchall()
        return [self._section_from_row(row) for row in rows]

    def get_section(self, section_id: str) -> ArchitectureStoredSection | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM architecture_sections WHERE id=?",
                (section_id,),
            ).fetchone()
        return self._section_from_row(row) if row else None

    def list_edges(self, snapshot_id: str) -> list[ArchitectureEdge]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT * FROM architecture_edges
                WHERE snapshot_id=? ORDER BY id""",
                (snapshot_id,),
            ).fetchall()
        return [self._edge_from_row(row) for row in rows]

    def get_edge(self, edge_id: str) -> ArchitectureEdge | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM architecture_edges WHERE id=?",
                (edge_id,),
            ).fetchone()
        return self._edge_from_row(row) if row else None

    def list_issues(self, snapshot_id: str) -> list[ArchitectureStoredIssue]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT * FROM architecture_issues
                WHERE snapshot_id=? ORDER BY severity,code,id""",
                (snapshot_id,),
            ).fetchall()
        return [self._issue_from_row(row) for row in rows]

    def get_issue(self, issue_id: str) -> ArchitectureStoredIssue | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM architecture_issues WHERE id=?",
                (issue_id,),
            ).fetchone()
        return self._issue_from_row(row) if row else None

    @staticmethod
    def _validation_issues(
        repository: str,
        documents: list[ArchitectureParseResult],
    ) -> list[ArchitectureIssue]:
        issues: list[ArchitectureIssue] = [
            issue for document in documents for issue in document.issues
        ]
        source_counts: dict[str, int] = defaultdict(int)
        stable_sources: dict[str, list[str]] = defaultdict(list)
        for document in documents:
            source_counts[document.source_uri] += 1
            if document.card:
                stable_sources[document.card.id].append(document.source_uri)
                if (
                    document.card.repository
                    and document.card.repository.casefold() != repository.casefold()
                ):
                    issues.append(ArchitectureIssue(
                        code="repository_mismatch",
                        severity="error",
                        message="The card repository does not match the sync repository.",
                        source_uri=document.source_uri,
                        field="repository",
                        detail={
                            "declared": document.card.repository,
                            "requested": repository,
                        },
                    ))
        for source_uri, count in source_counts.items():
            if count > 1:
                issues.append(ArchitectureIssue(
                    code="duplicate_source_uri",
                    severity="error",
                    message="A snapshot cannot contain the same source URI twice.",
                    source_uri=source_uri,
                    field="source_uri",
                    detail={"count": count},
                ))
        for stable_id, sources in stable_sources.items():
            if len(sources) > 1:
                issues.append(ArchitectureIssue(
                    code="duplicate_stable_id",
                    severity="error",
                    message="A snapshot cannot contain duplicate architecture card IDs.",
                    source_uri=sources[0],
                    field="id",
                    detail={"stable_id": stable_id, "sources": sorted(sources)},
                ))
        if not any(document.valid for document in documents):
            issues.append(ArchitectureIssue(
                code="no_valid_architecture_cards",
                severity="error",
                message="A snapshot needs at least one valid architecture card.",
                source_uri=".",
                detail={"document_count": len(documents)},
            ))
        return issues

    @staticmethod
    def _insert_document(
        conn: Any,
        snapshot_id: str,
        document: ArchitectureParseResult,
        created_at: str,
    ) -> str | None:
        if document.card is None or document.dialect is None:
            return None
        version_id = "adoc_" + _digest(
            snapshot_id, document.source_uri, document.content_hash,
        )
        conn.execute(
            """INSERT INTO architecture_document_versions(
            id,snapshot_id,stable_id,source_uri,dialect,title,declaration_json,
            body,content_hash,last_verified,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                version_id,
                snapshot_id,
                document.card.id,
                document.source_uri,
                document.dialect,
                document.card.title,
                document.card.model_dump_json(),
                document.body,
                document.content_hash,
                document.card.last_verified,
                created_at,
            ),
        )
        for section in document.sections:
            section_id = "asec_" + _digest(
                version_id, section.id, section.content_hash,
            )
            conn.execute(
                """INSERT INTO architecture_sections(
                id,document_version_id,stable_id,heading,heading_slug,ordinal,
                body,content_hash,evidence_class)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    section_id,
                    version_id,
                    section.id,
                    section.heading,
                    section.heading_slug,
                    section.ordinal,
                    section.body,
                    section.content_hash,
                    section.evidence_class,
                ),
            )
        return version_id

    @staticmethod
    def _insert_issue(
        conn: Any,
        snapshot_id: str,
        issue: ArchitectureIssue,
        index: int,
        created_at: str,
    ) -> None:
        issue_id = "aissue_" + _digest(
            snapshot_id, issue.source_uri, issue.code, str(index),
        )
        detail = {
            "message": issue.message,
            "field": issue.field,
            **issue.detail,
        }
        conn.execute(
            """INSERT INTO architecture_issues(
            id,snapshot_id,source_uri,code,severity,detail_json,evidence_class,created_at)
            VALUES(?,?,?,?,?,?,?,?)""",
            (
                issue_id,
                snapshot_id,
                issue.source_uri,
                issue.code,
                issue.severity,
                json.dumps(detail, sort_keys=True),
                issue.evidence_class,
                created_at,
            ),
        )

    @staticmethod
    def _insert_edge(
        conn: Any,
        *,
        snapshot_id: str,
        source_id: str,
        target_ref: str,
        target_id: str | None,
        relation_type: str,
        evidence_class: str,
        resolution_status: str,
        document_version_id: str | None,
        source_field: str,
        ordinal: int,
        created_at: str,
    ) -> None:
        edge_id = "aedge_" + _digest(
            snapshot_id,
            source_id,
            relation_type,
            target_ref,
            source_field,
            str(ordinal),
        )
        conn.execute(
            """INSERT INTO architecture_edges(
            id,snapshot_id,source_id,target_ref,target_id,relation_type,
            evidence_class,resolution_status,source_document_version_id,
            source_field,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                edge_id,
                snapshot_id,
                source_id,
                target_ref,
                target_id,
                relation_type,
                evidence_class,
                resolution_status,
                document_version_id,
                source_field,
                created_at,
            ),
        )

    def _materialize_edges(
        self,
        conn: Any,
        *,
        snapshot_id: str,
        repository: str,
        documents: list[ArchitectureParseResult],
        version_ids: dict[str, str],
        created_at: str,
    ) -> list[ArchitectureIssue]:
        issues: list[ArchitectureIssue] = []
        stable_versions: dict[str, list[str]] = defaultdict(list)
        for document in documents:
            if document.card and document.source_uri in version_ids:
                stable_versions[document.card.id].append(version_ids[document.source_uri])

        edge_ordinal = 0
        repository_id = _entity_id("repository", repository.casefold())
        for document in documents:
            if not document.card:
                continue
            version_id = version_ids.get(document.source_uri)
            if not version_id:
                continue
            self._insert_edge(
                conn,
                snapshot_id=snapshot_id,
                source_id=repository_id,
                target_ref=document.card.id,
                target_id=version_id,
                relation_type="CONTAINS",
                evidence_class="derived",
                resolution_status="resolved",
                document_version_id=version_id,
                source_field="repository",
                ordinal=edge_ordinal,
                created_at=created_at,
            )
            edge_ordinal += 1

            for section in document.sections:
                section_id = "asec_" + _digest(
                    version_id, section.id, section.content_hash,
                )
                self._insert_edge(
                    conn,
                    snapshot_id=snapshot_id,
                    source_id=section_id,
                    target_ref=document.card.id,
                    target_id=version_id,
                    relation_type="PART_OF",
                    evidence_class="derived",
                    resolution_status="resolved",
                    document_version_id=version_id,
                    source_field="sections",
                    ordinal=edge_ordinal,
                    created_at=created_at,
                )
                edge_ordinal += 1

            declarations = (
                ("main_files", "DESCRIBES", "file"),
                ("public_interfaces", "OWNS_CONTRACT", "interface"),
                ("provides", "PROVIDES", "capability"),
                ("safe_edit_points", "SAFE_EDIT_POINT", "safe-edit"),
                ("risk_areas", "RISK_AREA", "risk"),
                ("graph_rag_entities", "MENTIONS", "entity"),
            )
            for field, relation, target_kind in declarations:
                for target_ref in getattr(document.card, field):
                    self._insert_edge(
                        conn,
                        snapshot_id=snapshot_id,
                        source_id=version_id,
                        target_ref=target_ref,
                        target_id=_entity_id(target_kind, target_ref),
                        relation_type=relation,
                        evidence_class="declared",
                        resolution_status="resolved",
                        document_version_id=version_id,
                        source_field=field,
                        ordinal=edge_ordinal,
                        created_at=created_at,
                    )
                    edge_ordinal += 1

            for target_ref in document.card.depends_on:
                matches = stable_versions.get(target_ref, [])
                status = (
                    "resolved" if len(matches) == 1
                    else "ambiguous" if len(matches) > 1
                    else "unresolved"
                )
                target_id = matches[0] if len(matches) == 1 else None
                self._insert_edge(
                    conn,
                    snapshot_id=snapshot_id,
                    source_id=version_id,
                    target_ref=target_ref,
                    target_id=target_id,
                    relation_type="DEPENDS_ON",
                    evidence_class="declared",
                    resolution_status=status,
                    document_version_id=version_id,
                    source_field="depends_on",
                    ordinal=edge_ordinal,
                    created_at=created_at,
                )
                edge_ordinal += 1
                if status != "resolved":
                    issues.append(ArchitectureIssue(
                        code=f"{status}_edge",
                        severity="warning",
                        message=f"Declared dependency is {status}.",
                        source_uri=document.source_uri,
                        field="depends_on",
                        detail={"target_ref": target_ref},
                    ))

            for index, relationship in enumerate(document.card.relationships):
                relation = str(
                    relationship.get("type") or relationship.get("relation") or ""
                ).strip().upper()
                target_ref = str(relationship.get("target") or "").strip()
                if not _RELATION_RE.fullmatch(relation) or not target_ref:
                    issues.append(ArchitectureIssue(
                        code="invalid_relationship",
                        severity="warning",
                        message="An explicit relationship needs a valid type and target.",
                        source_uri=document.source_uri,
                        field=f"relationships.{index}",
                    ))
                    continue
                matches = stable_versions.get(target_ref, [])
                target_id = matches[0] if len(matches) == 1 else None
                status = (
                    "resolved" if target_id
                    else "ambiguous" if len(matches) > 1
                    else "unresolved"
                )
                self._insert_edge(
                    conn,
                    snapshot_id=snapshot_id,
                    source_id=version_id,
                    target_ref=target_ref,
                    target_id=target_id,
                    relation_type=relation,
                    evidence_class="declared",
                    resolution_status=status,
                    document_version_id=version_id,
                    source_field=f"relationships.{index}",
                    ordinal=edge_ordinal,
                    created_at=created_at,
                )
                edge_ordinal += 1
        return issues

    def activate(
        self,
        *,
        repository: str,
        documents: list[ArchitectureParseResult],
        repository_id: str | None = None,
        aliases: list[str] | None = None,
        source_revision: str = "",
        manifest_hash: str = "",
    ) -> ArchitectureSnapshot:
        if not repository.strip():
            raise ValueError("repository is required")
        if not documents:
            raise ValueError("at least one architecture document is required")
        repository = repository.strip()
        repository_id = repository_id or re.sub(
            r"[^a-z0-9._-]+", "-", repository.casefold(),
        ).strip("-")
        if not _REPOSITORY_ID_RE.fullmatch(repository_id):
            raise ValueError("repository_id must be a stable lower-case identifier")
        normalized_aliases = list(dict.fromkeys(
            alias.strip() for alias in (aliases or []) if alias.strip()
        ))
        corpus_hash = _corpus_hash(documents)
        manifest_hash = manifest_hash or hashlib.sha256(b"").hexdigest()
        snapshot_id = "asnap_" + _digest(
            repository_id,
            source_revision,
            manifest_hash,
            corpus_hash,
        )
        existing = self.get_snapshot(snapshot_id)
        if existing:
            return existing

        created_at = utc_now()
        validation_issues = self._validation_issues(repository, documents)
        valid_count = sum(document.valid for document in documents)
        with self.db.transaction() as conn:
            existing_repository = conn.execute(
                "SELECT created_at FROM architecture_repositories WHERE id=?",
                (repository_id,),
            ).fetchone()
            repository_created_at = (
                existing_repository["created_at"]
                if existing_repository else created_at
            )
            conn.execute(
                """INSERT INTO architecture_repositories(
                id,name,aliases_json,manifest_hash,created_at,updated_at)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,aliases_json=excluded.aliases_json,
                manifest_hash=excluded.manifest_hash,updated_at=excluded.updated_at""",
                (
                    repository_id,
                    repository,
                    json.dumps(normalized_aliases),
                    manifest_hash,
                    repository_created_at,
                    created_at,
                ),
            )
            conn.execute(
                """INSERT INTO architecture_snapshots(
                id,repository_id,repository,source_revision,manifest_hash,corpus_hash,status,
                document_count,valid_count,issue_count,created_at,activated_at)
                VALUES(?,?,?,?,?,?,'staging',?,?,0,?,NULL)""",
                (
                    snapshot_id,
                    repository_id,
                    repository,
                    source_revision,
                    manifest_hash,
                    corpus_hash,
                    len(documents),
                    valid_count,
                    created_at,
                ),
            )
            version_ids: dict[str, str] = {}
            inserted_sources: set[str] = set()
            for document in sorted(documents, key=lambda item: item.source_uri):
                if document.source_uri in inserted_sources:
                    continue
                inserted_sources.add(document.source_uri)
                version_id = self._insert_document(
                    conn, snapshot_id, document, created_at,
                )
                if version_id:
                    version_ids[document.source_uri] = version_id

            edge_issues = self._materialize_edges(
                conn,
                snapshot_id=snapshot_id,
                repository=repository,
                documents=documents,
                version_ids=version_ids,
                created_at=created_at,
            )
            all_issues = [*validation_issues, *edge_issues]
            for index, issue in enumerate(all_issues):
                self._insert_issue(
                    conn, snapshot_id, issue, index, created_at,
                )

            rejected = any(issue.severity == "error" for issue in validation_issues)
            status = "rejected" if rejected else "active"
            activated_at = None if rejected else created_at
            if not rejected:
                conn.execute(
                    """UPDATE architecture_snapshots SET status='historical'
                    WHERE repository_id=? AND status='active'""",
                    (repository_id,),
                )
            conn.execute(
                """UPDATE architecture_snapshots
                SET status=?,issue_count=?,activated_at=? WHERE id=?""",
                (status, len(all_issues), activated_at, snapshot_id),
            )
        result = self.get_snapshot(snapshot_id)
        if result is None:  # pragma: no cover - transaction contract guard
            raise RuntimeError("architecture snapshot disappeared after activation")
        return result
