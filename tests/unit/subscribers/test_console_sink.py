"""ConsoleSink unit tests."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime

import pytest

from lime_ref_postgres_mcp.domain.agent.agent_id import AgentId
from lime_ref_postgres_mcp.domain.auditing.agent_action_event import AgentActionEvent
from lime_ref_postgres_mcp.domain.auditing.event_outcome import EventOutcome
from lime_ref_postgres_mcp.domain.common.result import unwrap
from lime_ref_postgres_mcp.subscribers.console_sink import ConsoleSink

FORBIDDEN = frozenset({"payload", "response", "rows", "result", "body"})


@pytest.mark.asyncio
async def test_console_sink_jsonl() -> None:
    buf = io.StringIO()
    sink = ConsoleSink(stream=buf)
    event = AgentActionEvent(
        event_id="e1",
        ts=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
        agent_id=unwrap(AgentId.parse("agent-1")),
        request={"tool": "list_schemas", "args": {}},
        status="ok",
        outcome=EventOutcome(rows_count=1),
        duration_ms=3,
        meta={"request_id": "r1"},
    )
    await sink(event)
    line = buf.getvalue().strip()
    record = json.loads(line)
    assert record["event_id"] == "e1"
    assert record["ts"].endswith("Z")
    assert record["agent_id"] == "agent-1"
    assert record["request"] == {"tool": "list_schemas", "args": {}}
    assert record["status"] == "ok"
    assert record["outcome"] == {"rows_count": 1}
    assert record["duration_ms"] == 3
    assert record["meta"] == {"request_id": "r1"}
    keys = set(record) | set(record["request"]) | set(record["outcome"])
    assert FORBIDDEN.isdisjoint(keys)
    assert "rows_count" in record["outcome"]


@pytest.mark.asyncio
async def test_console_sink_omits_empty_outcome_fields() -> None:
    buf = io.StringIO()
    sink = ConsoleSink(stream=buf)
    event = AgentActionEvent(
        event_id="e2",
        ts=datetime(2026, 8, 1, tzinfo=UTC),
        agent_id=unwrap(AgentId.parse("a")),
        request={"tool": "x", "args": {"sql": "SELECT 1"}},
        status="denied",
        outcome=EventOutcome(reason_code="capability_denied"),
        duration_ms=None,
        meta={},
    )
    await sink(event)
    outcome = json.loads(buf.getvalue())["outcome"]
    assert outcome == {"reason_code": "capability_denied"}


@pytest.mark.asyncio
async def test_console_sink_full_outcome_and_naive_ts() -> None:
    buf = io.StringIO()
    sink = ConsoleSink(stream=buf)
    event = AgentActionEvent(
        event_id="e3",
        ts=datetime(2026, 8, 1, 12, 0, 0),  # naive → treat as UTC
        agent_id=unwrap(AgentId.parse("a")),
        request={"tool": "execute_write_query", "args": {}},
        status="ok",
        outcome=EventOutcome(
            reason_code=None,
            missing_capabilities=("WRITE_DATA",),
            statement_class="DML",
            rows_count=None,
            affected_rows=2,
        ),
        duration_ms=1,
        meta={},
    )
    await sink(event)
    record = json.loads(buf.getvalue())
    assert record["ts"].endswith("Z")
    assert record["outcome"] == {
        "missing_capabilities": ["WRITE_DATA"],
        "statement_class": "DML",
        "affected_rows": 2,
    }
