"""Thin handler unit tests."""

from __future__ import annotations

import json

import pytest
from tests.support.build_test_runtime import wire_invoke

from lime_ref_postgres_mcp.presentation.mcp.handlers import (
    admin_tools,
    data_tools,
    schema_tools,
)


def _status(result: object) -> str:
    text = result.content[0].text  # type: ignore[attr-defined]
    return json.loads(text)["status"]


@pytest.mark.asyncio
async def test_list_schemas_handler_ok() -> None:
    invoke, _bus = wire_invoke()
    result = await schema_tools.list_schemas(invoke, "tok", {}, "req-1")
    assert result.is_error is False
    assert _status(result) == "ok"


@pytest.mark.asyncio
async def test_list_schemas_missing_bearer() -> None:
    invoke, bus = wire_invoke()
    result = await schema_tools.list_schemas(invoke, None, {}, "req-1")
    assert result.is_error is True
    assert _status(result) == "error"
    assert bus.events == []


@pytest.mark.asyncio
async def test_list_tables_passes_schema() -> None:
    invoke, _bus = wire_invoke()
    result = await schema_tools.list_tables(invoke, "tok", {"schema": "public"}, "req-1")
    assert _status(result) == "ok"


@pytest.mark.asyncio
async def test_get_table_schema() -> None:
    invoke, _bus = wire_invoke()
    result = await schema_tools.get_table_schema(
        invoke, "tok", {"schema": "public", "table": "t"}, "req-1"
    )
    assert _status(result) == "ok"


@pytest.mark.asyncio
async def test_select_rows() -> None:
    invoke, _bus = wire_invoke()
    result = await data_tools.select_rows(
        invoke, "tok", {"schema": "public", "table": "t", "limit": 1}, "req-1"
    )
    assert _status(result) == "ok"


@pytest.mark.asyncio
async def test_execute_readonly() -> None:
    invoke, _bus = wire_invoke()
    result = await data_tools.execute_readonly_query(invoke, "tok", {"sql": "SELECT 1"}, "req-1")
    assert _status(result) == "ok"


@pytest.mark.asyncio
async def test_explain() -> None:
    invoke, _bus = wire_invoke()
    result = await data_tools.explain_query_plan(invoke, "tok", {"sql": "SELECT 1"}, "req-1")
    assert _status(result) == "ok"


@pytest.mark.asyncio
async def test_write_class_denied_with_fake_analyzer() -> None:
    invoke, bus = wire_invoke()
    write = await data_tools.execute_write_query(
        invoke, "tok", {"sql": "INSERT INTO t VALUES (1)"}, "req-1"
    )
    # FakeSqlAnalyzer defaults to READ class → statement_class_denied
    assert _status(write) == "denied"
    assert write.is_error is True
    assert bus.events


@pytest.mark.asyncio
async def test_stats_capability_denied() -> None:
    invoke, bus = wire_invoke()
    stats = await admin_tools.get_database_stats(invoke, "tok", {}, "req-1")
    assert _status(stats) == "denied"
    assert bus.events[0].outcome.reason_code == "capability_denied"
