"""In-process EventBus — sequential await; sink errors do not alter tool Result."""

from __future__ import annotations

from lime_ref_postgres_mcp.application.ports.events import EventHandler
from lime_ref_postgres_mcp.bootstrap.observability import log, metrics
from lime_ref_postgres_mcp.domain.auditing.agent_action_event import AgentActionEvent


class InProcessEventBus:
    """Ordered emit: await each subscriber; swallow handler exceptions."""

    def __init__(self) -> None:
        self._handlers: list[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    async def emit(self, event: AgentActionEvent) -> None:
        for handler in self._handlers:
            try:
                await handler(event)
            except Exception as exc:  # noqa: BLE001 — process-level; never change tool Result
                log(
                    "events",
                    "sink.error",
                    level="ERROR",
                    error_type=type(exc).__name__,
                    event_id=event.event_id,
                )
                metrics.inc("mcp_sink_error_total")


__all__ = ["InProcessEventBus"]
