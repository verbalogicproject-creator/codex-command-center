from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from ..db import Database
from ..embeddings import (
    EmbeddingProvider,
    cosine_scores,
    normalize_vector,
    vector_blob,
    vector_from_blob,
)
from ..models import utc_now
from .models import ArchitectureDocumentVersion, ArchitectureStoredSection


def canonical_section_surface(
    section: ArchitectureStoredSection,
    document: ArchitectureDocumentVersion,
) -> str:
    """Provider-neutral architecture text without IDs or arbitrary metadata."""
    declaration = document.declaration
    lines = [
        "entity_type: architecture_section",
        f"repository: {declaration.get('repository') or ''}",
        f"kind: {declaration.get('kind') or 'architecture_doc'}",
        f"status: {declaration.get('status') or 'undocumented'}",
        f"title: {document.title}",
        f"heading: {section.heading}",
        f"owner_area: {declaration.get('owner_area') or ''}",
    ]
    for field in (
        "provides",
        "public_interfaces",
        "depends_on",
        "safe_edit_points",
        "risk_areas",
        "graph_rag_entities",
    ):
        values = declaration.get(field) or []
        lines.append(f"{field}: {', '.join(str(value) for value in values)}")
    lines.append(f"content: {section.body}")
    return "\n".join(lines)


@dataclass(frozen=True)
class ArchitectureEmbeddingSync:
    indexed: int
    unchanged: int
    failed: int
    eligible: int
    coverage: float
    degraded: bool


class ArchitectureEmbeddingStore:
    """Version-scoped dense index for declared architecture sections."""

    def __init__(self, db: Database, provider: EmbeddingProvider):
        self.db = db
        self.provider = provider

    @property
    def scope(self) -> tuple[str, str, int]:
        return (
            self.provider.name,
            self.provider.model,
            self.provider.dimensions,
        )

    def _sections(
        self, snapshot_id: str,
    ) -> list[tuple[ArchitectureStoredSection, ArchitectureDocumentVersion]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT s.*,d.id AS parent_id,d.snapshot_id,d.stable_id AS
                parent_stable_id,d.source_uri,d.dialect,d.title,
                d.declaration_json,d.body AS parent_body,
                d.content_hash AS parent_content_hash,d.last_verified,d.created_at
                FROM architecture_sections s
                JOIN architecture_document_versions d
                  ON d.id=s.document_version_id
                WHERE d.snapshot_id=?
                ORDER BY d.source_uri,s.ordinal""",
                (snapshot_id,),
            ).fetchall()
        result = []
        for row in rows:
            values = dict(row)
            section = ArchitectureStoredSection(
                id=values["id"],
                document_version_id=values["document_version_id"],
                stable_id=values["stable_id"],
                heading=values["heading"],
                heading_slug=values["heading_slug"],
                ordinal=values["ordinal"],
                body=values["body"],
                content_hash=values["content_hash"],
                evidence_class=values["evidence_class"],
            )
            document = ArchitectureDocumentVersion(
                id=values["parent_id"],
                snapshot_id=values["snapshot_id"],
                stable_id=values["parent_stable_id"],
                source_uri=values["source_uri"],
                dialect=values["dialect"],
                title=values["title"],
                declaration=json.loads(values["declaration_json"]),
                body=values["parent_body"],
                content_hash=values["parent_content_hash"],
                last_verified=values["last_verified"],
                created_at=values["created_at"],
            )
            result.append((section, document))
        return result

    def coverage(self, snapshot_id: str) -> tuple[int, int, float]:
        provider, model, dimensions = self.scope
        with self.db.connect() as conn:
            eligible = int(conn.execute(
                """SELECT COUNT(*) FROM architecture_sections s
                JOIN architecture_document_versions d
                  ON d.id=s.document_version_id
                WHERE d.snapshot_id=?""",
                (snapshot_id,),
            ).fetchone()[0])
            indexed = int(conn.execute(
                """SELECT COUNT(*) FROM architecture_section_embeddings e
                JOIN architecture_sections s ON s.id=e.section_id
                JOIN architecture_document_versions d
                  ON d.id=s.document_version_id
                WHERE d.snapshot_id=? AND e.provider=? AND e.model=?
                  AND e.dimensions=?""",
                (snapshot_id, provider, model, dimensions),
            ).fetchone()[0])
        return eligible, indexed, indexed / eligible if eligible else 1.0

    def sync(self, snapshot_id: str) -> ArchitectureEmbeddingSync:
        sections = self._sections(snapshot_id)
        wanted: dict[str, tuple[str, str]] = {}
        for section, document in sections:
            surface = canonical_section_surface(section, document)
            wanted[section.id] = (
                hashlib.sha256(surface.encode("utf-8")).hexdigest(),
                surface,
            )
        provider, model, dimensions = self.scope
        with self.db.connect() as conn:
            cached = {
                row["section_id"]: row["content_hash"]
                for row in conn.execute(
                    """SELECT e.section_id,e.content_hash
                    FROM architecture_section_embeddings e
                    JOIN architecture_sections s ON s.id=e.section_id
                    JOIN architecture_document_versions d
                      ON d.id=s.document_version_id
                    WHERE d.snapshot_id=? AND e.provider=? AND e.model=?
                      AND e.dimensions=?""",
                    (snapshot_id, provider, model, dimensions),
                )
            }
        changed = [
            section_id for section_id, (digest, _) in wanted.items()
            if cached.get(section_id) != digest
        ]
        failed = 0
        try:
            vectors = self.provider.embed_documents(
                [wanted[section_id][1] for section_id in changed]
            )
            if len(vectors) != len(changed):
                raise ValueError("wrong architecture embedding count")
            with self.db.transaction() as conn:
                for section_id, vector in zip(changed, vectors, strict=True):
                    if len(vector) != dimensions:
                        raise ValueError(
                            "wrong architecture embedding dimensions"
                        )
                    conn.execute(
                        """INSERT INTO architecture_section_embeddings(
                        section_id,content_hash,provider,model,dimensions,vector,
                        updated_at) VALUES(?,?,?,?,?,?,?)
                        ON CONFLICT(section_id) DO UPDATE SET
                        content_hash=excluded.content_hash,
                        provider=excluded.provider,model=excluded.model,
                        dimensions=excluded.dimensions,vector=excluded.vector,
                        updated_at=excluded.updated_at""",
                        (
                            section_id,
                            wanted[section_id][0],
                            provider,
                            model,
                            dimensions,
                            vector_blob(normalize_vector(vector)),
                            utc_now(),
                        ),
                    )
        except Exception:
            failed = len(changed)
        eligible, indexed, coverage = self.coverage(snapshot_id)
        return ArchitectureEmbeddingSync(
            indexed=len(changed) - failed,
            unchanged=max(eligible - len(changed), 0),
            failed=failed,
            eligible=eligible,
            coverage=coverage,
            degraded=failed > 0 or coverage < 1,
        )

    def query(
        self, snapshot_id: str, text: str,
    ) -> tuple[dict[str, float], bool]:
        provider, model, dimensions = self.scope
        ids: list[str] = []
        vectors: list[list[float]] = []
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT e.section_id,e.vector
                FROM architecture_section_embeddings e
                JOIN architecture_sections s ON s.id=e.section_id
                JOIN architecture_document_versions d
                  ON d.id=s.document_version_id
                WHERE d.snapshot_id=? AND e.provider=? AND e.model=?
                  AND e.dimensions=?
                ORDER BY e.section_id""",
                (snapshot_id, provider, model, dimensions),
            ).fetchall()
        for row in rows:
            vector = vector_from_blob(row["vector"])
            if len(vector) != dimensions:
                continue
            ids.append(row["section_id"])
            vectors.append(normalize_vector(vector))
        if not ids:
            return {}, bool(self.coverage(snapshot_id)[0])
        try:
            query = self.provider.embed_query(text)
            if len(query) != dimensions:
                raise ValueError("wrong architecture query dimensions")
            scores = cosine_scores(vectors, query)
            return dict(zip(ids, map(float, scores), strict=True)), False
        except Exception:
            return {}, True
