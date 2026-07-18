"""Vendored frontmatter declaration layer from frontmatter_rag commit a3b835b."""

from .parse import first_h1, parse_frontmatter
from .presets import ARCHITECTURE_AI_CARD_REQUIRED_SLOTS, COMMAND_CENTER_AI_CARD
from .schema import Facet, FrontmatterSchema

__all__ = [
    "ARCHITECTURE_AI_CARD_REQUIRED_SLOTS", "COMMAND_CENTER_AI_CARD", "Facet",
    "FrontmatterSchema", "first_h1", "parse_frontmatter",
]
