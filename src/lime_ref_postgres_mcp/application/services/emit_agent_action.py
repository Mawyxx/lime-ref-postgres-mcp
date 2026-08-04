"""EmitAgentAction — ctx + EventOutcome → AgentActionEvent (no AgentReply)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from lime_ref_postgres_mcp.application.context.request_context import RequestContext
from lime_ref_postgres_mcp.application.ports.clock import Clock, IdGenerator
from lime_ref_postgres_mcp.application.ports.events import EventBus
from lime_ref_postgres_mcp.bootstrap.observability import log, metrics
from lime_ref_postgres_mcp.domain.auditing.agent_action_event import AgentActionEvent, EventStatus
from lime_ref_postgres_mcp.domain.auditing.event_outcome import EventOutcome

_SECRET_KEYS = frozenset(
    {
        "authorization",
        "bearer",
        "bearer_token",
        "token",
        "passport",
        "password",
        "secret",
        "api_key",
    }
)


def sanitize_args(args: Mapping[str, Any]) -> dict[str, Any]:
    """Drop secret-like keys from event.request.args."""
    return {k: v for k, v in args.items() if k.lower() not in _SECRET_KEYS}


@dataclass(frozen=True, slots=True)
class EmitAgentActionService:
    event_bus: EventBus
    clock: Clock
    ids: IdGenerator

    async def emit(
        self,
        ctx: RequestContext,
        status: EventStatus,
        outcome: EventOutcome,
    ) -> None:
        now = self.clock.now_utc()
        duration_ms = int((now - ctx.started_at).total_seconds() * 1000)
        event = AgentActionEvent(
            event_id=self.ids.new_event_id(),
            ts=now,
            agent_id=ctx.agent.agent_id,
            request={"tool": ctx.tool.value, "args": sanitize_args(ctx.args)},
            status=status,
            outcome=outcome,
            duration_ms=duration_ms,
            meta={"domain": ctx.agent.domain, "request_id": ctx.request_id},
        )
        await self.event_bus.emit(event)
        log(
            "events",
            "emit",
            status=status,
            tool=ctx.tool.value,
            request_id=ctx.request_id,
            agent_id=str(ctx.agent.agent_id),
            duration_ms=duration_ms,
        )
        metrics.inc("mcp_emit_total", status=status)


__all__ = ["EmitAgentActionService", "sanitize_args"]
