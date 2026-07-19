"""Command Center v3 memory service."""

from typing import Any


def create_app(*args: Any, **kwargs: Any):
    """Load the browser API lazily so MCP-only imports stay isolated."""

    from .app import create_app as factory

    return factory(*args, **kwargs)


__all__ = ["create_app"]
