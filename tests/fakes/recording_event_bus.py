"""Recording EventBus for assertions."""

from __future__ import annotations

from lime_ref_postgres_mcp.application.ports.events import EventHandler
from lime_ref_postgres_mcp.domain.auditing.agent_action_event import AgentActionEvent


class RecordingEventBus:
    def __init__(self) -> None:
        self.events: list[AgentActionEvent] = []
        self._handlers: list[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    async def emit(self, event: AgentActionEvent) -> None:
        self.events.append(event)
        for handler in self._handlers:
            await handler(event)


__all__ = ["RecordingEventBus"]
