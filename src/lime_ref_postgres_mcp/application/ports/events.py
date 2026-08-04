"""EventBus port — authorized-path audit emit."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from lime_ref_postgres_mcp.domain.auditing.agent_action_event import AgentActionEvent

EventHandler = Callable[[AgentActionEvent], Awaitable[None]]


class EventBus(Protocol):
    def subscribe(self, handler: EventHandler) -> None: ...

    async def emit(self, event: AgentActionEvent) -> None: ...


__all__ = ["EventBus", "EventHandler"]
