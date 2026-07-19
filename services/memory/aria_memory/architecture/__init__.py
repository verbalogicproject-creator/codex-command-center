"""Provider-neutral architecture declaration parsing and validation."""

from .chunking import chunk_by_h2
from .compiler import ArchitectureCompiler
from .embeddings import (
    ArchitectureEmbeddingStore,
    ArchitectureEmbeddingSync,
    canonical_section_surface,
)
from .health import build_architecture_health
from .lint import ArchitectureLintReport, lint_architecture_document, scaffold_ai_card
from .manifest import (
    ArchitectureInventory,
    ArchitectureManifest,
    find_repository_root,
    load_architecture_manifest,
    scan_architecture_repository,
)
from .models import (
    ArchitectureCard,
    ArchitectureBrief,
    ArchitectureBriefRequest,
    ArchitectureDialect,
    ArchitectureDocumentVersion,
    ArchitectureEdge,
    ArchitectureIssue,
    ArchitectureParseResult,
    ArchitectureRepository,
    ArchitectureRepositoryIdentity,
    ArchitectureSection,
    ArchitectureSnapshot,
    ArchitectureSyncRequest,
    ArchitectureSyncResponse,
    ArchitectureStoredIssue,
    ArchitectureStoredSection,
)
from .parser import (
    MAX_DOCUMENT_BYTES,
    REQUIRED_CARD_SLOTS,
    parse_architecture_document,
)
from .store import ArchitectureStore

__all__ = [
    "ArchitectureCard",
    "ArchitectureBrief",
    "ArchitectureBriefRequest",
    "ArchitectureCompiler",
    "ArchitectureDialect",
    "ArchitectureDocumentVersion",
    "ArchitectureEmbeddingStore",
    "ArchitectureEmbeddingSync",
    "ArchitectureEdge",
    "ArchitectureIssue",
    "ArchitectureInventory",
    "ArchitectureLintReport",
    "ArchitectureManifest",
    "ArchitectureParseResult",
    "ArchitectureRepository",
    "ArchitectureRepositoryIdentity",
    "ArchitectureSection",
    "ArchitectureSnapshot",
    "ArchitectureSyncRequest",
    "ArchitectureSyncResponse",
    "ArchitectureStoredIssue",
    "ArchitectureStoredSection",
    "ArchitectureStore",
    "MAX_DOCUMENT_BYTES",
    "REQUIRED_CARD_SLOTS",
    "build_architecture_health",
    "canonical_section_surface",
    "chunk_by_h2",
    "find_repository_root",
    "lint_architecture_document",
    "load_architecture_manifest",
    "parse_architecture_document",
    "scan_architecture_repository",
    "scaffold_ai_card",
]
