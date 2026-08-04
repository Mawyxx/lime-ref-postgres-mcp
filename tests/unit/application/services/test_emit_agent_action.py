"""EmitAgentAction unit tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.policy import FakePolicyStore
from tests.fakes.recording_event_bus import RecordingEventBus
from tests.fakes.sequence_ids import SequenceIds

from lime_ref_postgres_mcp.application.context.request_context import (
    PolicySnapshot,
    RequestContext,
)
from lime_ref_postgres_mcp.application.services.emit_agent_action import (
    EmitAgentActionService,
    sanitize_args,
)
from lime_ref_postgres_mcp.domain.access.authorized_agent import AuthorizedAgent
from lime_ref_postgres_mcp.domain.access.capability import ToolCapability
from lime_ref_postgres_mcp.domain.agent.agent_id import AgentId
from lime_ref_postgres_mcp.domain.auditing.event_outcome import EventOutcome
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName
from lime_ref_postgres_mcp.domain.common.result import unwrap


def test_sanitize_args_drops_secrets() -> None:
    cleaned = sanitize_args({"sql": "SELECT 1", "bearer_token": "x", "Authorization": "y"})
    assert cleaned == {"sql": "SELECT 1"}


@pytest.mark.asyncio
async def test_emit_builds_event_without_payload() -> None:
    bus = RecordingEventBus()
    clock = FixedClock()
    svc = EmitAgentActionService(event_bus=bus, clock=clock, ids=SequenceIds())
    doc = FakePolicyStore().document
    ctx = RequestContext(
        request_id="req-1",
        agent=AuthorizedAgent(
            agent_id=unwrap(AgentId.parse("agent_ok")),
            permissions=frozenset({ToolCapability.READ_DATA}),
            domain="example.com",
        ),
        tool=ToolName.SELECT_ROWS,
        args={"schema": "public", "table": "t", "token": "secret"},
        started_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
        policy=PolicySnapshot(document=doc, loaded_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)),
    )
    clock.advance(1.5)
    await svc.emit(ctx, "ok", EventOutcome(rows_count=3))
    assert len(bus.events) == 1
    event = bus.events[0]
    assert event.status == "ok"
    assert event.outcome.rows_count == 3
    assert "token" not in event.request["args"]
    assert event.duration_ms == 1500
    assert "payload" not in event.request
    assert "rows" not in event.request
