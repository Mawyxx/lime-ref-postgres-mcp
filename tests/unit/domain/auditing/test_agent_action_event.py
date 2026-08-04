"""AgentActionEvent / EventOutcome shape tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from lime_ref_postgres_mcp.domain.agent.agent_id import AgentId
from lime_ref_postgres_mcp.domain.auditing.agent_action_event import AgentActionEvent
from lime_ref_postgres_mcp.domain.auditing.event_outcome import EventOutcome
from lime_ref_postgres_mcp.domain.common.result import unwrap


def test_event_outcome_defaults() -> None:
    outcome = EventOutcome()
    assert outcome.reason_code is None
    assert outcome.missing_capabilities == ()
    assert outcome.statement_class is None
    assert outcome.rows_count is None
    assert outcome.affected_rows is None


def test_agent_action_event_construction() -> None:
    agent = unwrap(AgentId.parse("agent_1"))
    ts = datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)
    event = AgentActionEvent(
        event_id="evt-1",
        ts=ts,
        agent_id=agent,
        request={"tool": "list_schemas", "args": {}},
        status="ok",
        outcome=EventOutcome(rows_count=3),
        duration_ms=12,
        meta={"request_id": "req-1", "domain": "lime.pics"},
    )
    assert event.status == "ok"
    assert event.outcome.rows_count == 3
    assert "payload" not in event.request
    assert not hasattr(event, "payload")


def test_event_immutability() -> None:
    agent = unwrap(AgentId.parse("agent_1"))
    event = AgentActionEvent(
        event_id="evt-1",
        ts=datetime(2026, 7, 31, tzinfo=UTC),
        agent_id=agent,
        request={"tool": "select_rows", "args": {}},
        status="denied",
        outcome=EventOutcome(reason_code="capability_denied"),
        duration_ms=None,
        meta={},
    )
    with pytest.raises(AttributeError):
        event.status = "ok"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        event.outcome.reason_code = "x"  # type: ignore[misc]
