"""Database success payload for AgentReply + EventOutcome counters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DbPayload:
    """Gateway success: full payload for MCP + counters for audit only."""

    payload: Any
    rows_count: int | None = None
    affected_rows: int | None = None


__all__ = ["DbPayload"]
