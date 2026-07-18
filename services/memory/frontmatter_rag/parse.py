"""Markdown frontmatter parser adapted from frontmatter_rag 0.1.0."""

from __future__ import annotations

import re
from typing import Any

import yaml

_FRONTMATTER = re.compile(r"^﻿?---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)
_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def parse_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    match = _FRONTMATTER.match(text)
    if not match:
        return None, text
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None, text
    return (data, text[match.end():]) if isinstance(data, dict) else (None, text)


def first_h1(body: str) -> str | None:
    match = _H1.search(body)
    return match.group(1).strip() if match else None


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []
