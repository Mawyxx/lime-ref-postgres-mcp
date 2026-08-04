"""contextvars bind/clear + traceparent + async isolation."""

from __future__ import annotations

import asyncio

from lime_ref_postgres_mcp.bootstrap.observability.context import (
    bind_context,
    clear_context,
    get_bound,
    parse_traceparent,
)
from lime_ref_postgres_mcp.bootstrap.observability.logging import build_record


def setup_function() -> None:
    clear_context()


def test_bind_clear() -> None:
    bind_context(request_id="r1", agent_id="a1")
    assert get_bound() == {"request_id": "r1", "agent_id": "a1"}
    clear_context()
    assert get_bound() == {}


def test_bound_merged_into_record() -> None:
    bind_context(request_id="r9")
    record = build_record("mcp", "tools.call.start", tool="x")
    assert record["request_id"] == "r9"
    clear_context()


def test_bind_skips_none() -> None:
    bind_context(request_id="r1", agent_id=None)
    assert get_bound() == {"request_id": "r1"}


def test_parse_traceparent() -> None:
    fields = parse_traceparent("00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01")
    assert fields["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
    assert fields["parent_span_id"] == "b7ad6b7169203331"
    assert parse_traceparent("bogus") == {}
    assert parse_traceparent(None) == {}
    assert parse_traceparent("   ") == {}


async def _task(value: str) -> str:
    bind_context(request_id=value)
    await asyncio.sleep(0)
    rid = str(get_bound().get("request_id", ""))
    clear_context()
    return rid


def test_async_no_cross_task_leak() -> None:
    async def run() -> None:
        a, b = await asyncio.gather(_task("ra"), _task("rb"))
        assert {a, b} == {"ra", "rb"}

    asyncio.run(run())
