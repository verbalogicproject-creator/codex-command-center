"""Transparent intent routing adapted from declared_core 0.1.0."""

from __future__ import annotations

import re
from dataclasses import dataclass

Weights = tuple[float, float, float, float]

PROFILES: dict[str, Weights] = {
    "exact_match": (1.00, 0.20, 0.40, 0.30),
    "capability_check": (0.85, 0.35, 0.70, 0.45),
    "debugging": (0.70, 0.60, 0.95, 0.45),
    "workflow": (0.60, 0.95, 0.60, 0.50),
    "comparison": (0.60, 0.45, 0.65, 0.85),
    "goal_based": (0.55, 0.85, 0.60, 0.75),
    "exploratory": (0.45, 0.75, 0.50, 0.95),
    "semantic": (0.60, 0.50, 0.55, 0.85),
}

_PATTERNS = [
    ("exact_match", re.compile(r'"[^"]+"|\bexact(ly)?\b|\bverbatim\b|--\w', re.I), .9),
    ("debugging", re.compile(r"\b(error|bug|fail|broken|crash|debug|regression)\b", re.I), .9),
    ("comparison", re.compile(r"\b(vs\.?|versus|compare|difference|trade-?offs?)\b", re.I), .9),
    ("workflow", re.compile(r"\b(how (do|to|can) i|steps? to|set up|configure|install)\b", re.I), .9),
    ("capability_check", re.compile(r"^\s*(can|does|is|are|could|will|should)\b", re.I), .85),
    ("goal_based", re.compile(r"\b(build|create|implement|make|design|add|write|need to)\b", re.I), .6),
    ("exploratory", re.compile(r"\b(explore|overview|tell me about|show me|what (is|are))\b", re.I), .6),
]


@dataclass(frozen=True)
class IntentResult:
    intent: str
    confidence: float
    weights: Weights


def classify_intent(query: str) -> IntentResult:
    for intent, pattern, confidence in _PATTERNS:
        if pattern.search(query or ""):
            return IntentResult(intent, confidence, PROFILES[intent])
    return IntentResult("semantic", .3, PROFILES["semantic"])
