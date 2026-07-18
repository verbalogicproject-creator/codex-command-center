"""Command Center's extended AI-card mapping."""

from .schema import Facet, FrontmatterSchema

ARCHITECTURE_AI_CARD_REQUIRED_SLOTS = (
    "id",
    "kind",
    "audience",
    "status",
    "owner_area",
    "main_files",
    "public_interfaces",
    "provides",
    "depends_on",
    "safe_edit_points",
    "risk_areas",
    "graph_rag_entities",
    "last_verified",
)

COMMAND_CENTER_AI_CARD = FrontmatterSchema(
    facets=(
        Facet("provides", "text"),
        Facet("public_interfaces", "text"),
        Facet("safe_edit_points", "text"),
        Facet("risk_areas", "text"),
        Facet("graph_rag_entities", "tag"),
        Facet("depends_on", "tag"),
        Facet("main_files", "tag"),
        Facet("kind", "cluster"),
        Facet("status", "cluster"),
        Facet("owner_area", "cluster"),
        Facet("audience", "cluster"),
    ),
    id_key="id",
    title_key="title",
    timestamp_key="last_verified",
)
