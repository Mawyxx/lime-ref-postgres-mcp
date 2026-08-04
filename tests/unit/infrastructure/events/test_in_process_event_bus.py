"""InProcessEventBus unit tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from lime_ref_postgres_mcp.domain.agent.agent_id import AgentId
from lime_ref_postgres_mcp.domain.auditing.agent_action_event import AgentActionEvent
from lime_ref_postgres_mcp.domain.auditing.event_outcome import EventOutcome
from lime_ref_postgres_mcp.domain.common.result import unwrap
from lime_ref_postgres_mcp.infrastructure.events.in_process_event_bus import InProcessEventBus


def _event() -> AgentActionEvent:
    return AgentActionEvent(
        event_id="e1",
        ts=datetime(2026, 8, 1, tzinfo=UTC),
        agent_id=unwrap(AgentId.parse("a")),
        request={"tool": "list_schemas", "args": {}},
        status="ok",
        outcome=EventOutcome(),
        duration_ms=1,
        meta={},
    )


@pytest.mark.asyncio
async def test_emit_calls_handlers_in_order() -> None:
    bus = InProcessEventBus()
    seen: list[str] = []

    async def h1(event: AgentActionEvent) -> None:
        seen.append("h1")

    async def h2(event: AgentActionEvent) -> None:
        seen.append("h2")

    bus.subscribe(h1)
    bus.subscribe(h2)
    await bus.emit(_event())
    assert seen == ["h1", "h2"]


@pytest.mark.asyncio
async def test_handler_error_swallowed() -> None:
    bus = InProcessEventBus()
    seen: list[str] = []

    async def boom(event: AgentActionEvent) -> None:
        raise RuntimeError("sink fail")

    async def ok(event: AgentActionEvent) -> None:
        del event
        seen.append("ok")

    bus.subscribe(boom)
    bus.subscribe(ok)
    await bus.emit(_event())
    assert seen == ["ok"]
