"""AgentActionEvent shape (immutable; emit is P2)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from lime_ref_postgres_mcp.domain.agent.agent_id import AgentId
from lime_ref_postgres_mcp.domain.auditing.event_outcome import EventOutcome

EventStatus = Literal["ok", "error", "denied"]


@dataclass(frozen=True, slots=True)
class AgentActionEvent:
    """Authorized-path audit event — never carries agent response body."""

    event_id: str
    ts: datetime
    agent_id: AgentId
    request: Mapping[str, Any]
    status: EventStatus
    outcome: EventOutcome
    duration_ms: int | None
    meta: Mapping[str, Any]


__all__ = ["AgentActionEvent", "EventStatus"]
