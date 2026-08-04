"""Event outcome card — audit only, never agent payload."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EventOutcome:
    """Counters/codes for AgentActionEvent (no rows / LLM body)."""

    reason_code: str | None = None
    missing_capabilities: tuple[str, ...] = ()
    statement_class: str | None = None
    rows_count: int | None = None
    affected_rows: int | None = None


__all__ = ["EventOutcome"]
