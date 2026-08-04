"""Process log schema constants (PRD §8 / ADR-003)."""

from __future__ import annotations

SCHEMA_ID = "lime.mcp.process_log.v1"

COMPONENTS = frozenset(
    {
        "serve",
        "identity",
        "policy",
        "establish",
        "authorize",
        "db",
        "events",
        "mcp",
        "metrics",
    }
)

__all__ = ["COMPONENTS", "SCHEMA_ID"]
