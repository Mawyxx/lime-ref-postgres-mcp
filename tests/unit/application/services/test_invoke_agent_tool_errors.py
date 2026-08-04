"""InvokeAgentToolService — deny/error branch coverage."""

from __future__ import annotations

import pytest
from tests.fakes.database import FakeDatabaseGateway
from tests.fakes.sql_analyzer import FakeSqlAnalyzer
from tests.support.build_test_runtime import wire_invoke

from lime_ref_postgres_mcp.application.commands.invoke_agent_tool import InvokeAgentToolCommand
from lime_ref_postgres_mcp.application.services.invoke_agent_tool import _authz_to_reply_and_outcome
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName
from lime_ref_postgres_mcp.domain.common.errors import (
    CapabilityDenied,
    DatabaseFault,
    SqlParseFault,
)
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, unwrap


def test_capability_denied_missing_not_tuple() -> None:
    err = CapabilityDenied(
        invariant_id="access.capability_denied",
        message="denied",
        context={"missing": ["WRITE_DATA"]},
    )
    reply, outcome = _authz_to_reply_and_outcome(err)
    assert reply.status == "denied"
    assert outcome.missing_capabilities == ("WRITE_DATA",)


def test_capability_denied_missing_invalid_type() -> None:
    err = CapabilityDenied(
        invariant_id="access.capability_denied",
        message="denied",
        context={"missing": "WRITE_DATA"},
    )
    _, outcome = _authz_to_reply_and_outcome(err)
    assert outcome.missing_capabilities == ()


@pytest.mark.asyncio
async def test_sql_parse_fault_emits_denied() -> None:
    analyzer = FakeSqlAnalyzer()
    analyzer.set_result(
        "SELEC 1",
        Err(
            SqlParseFault(
                invariant_id="sql.parse_fault",
                message="syntax error",
                context={"parse_error": "syntax error"},
            )
        ),
    )
    invoke, bus = wire_invoke(analyzer=analyzer)
    result = await invoke.execute(
        InvokeAgentToolCommand(
            bearer_token="tok",
            tool=ToolName.EXECUTE_READONLY_QUERY,
            args={"sql": "SELEC 1"},
        )
    )
    assert isinstance(result, Ok)
    assert unwrap(result).status == "denied"
    assert bus.events[0].outcome.reason_code == "sql_parse_fault"


@pytest.mark.asyncio
async def test_tool_input_invalid_emits_denied() -> None:
    invoke, bus = wire_invoke()
    result = await invoke.execute(
        InvokeAgentToolCommand(
            bearer_token="tok",
            tool=ToolName.LIST_TABLES,
            args={},
        )
    )
    assert isinstance(result, Ok)
    assert unwrap(result).status == "denied"
    assert bus.events[0].outcome.reason_code == "tool_input_invalid"


@pytest.mark.asyncio
async def test_database_fault_emits_error() -> None:
    db = FakeDatabaseGateway()
    db.fault = DatabaseFault(
        invariant_id="database.fault",
        message="connection lost",
        context={},
    )
    invoke, bus = wire_invoke(database=db)
    result = await invoke.execute(
        InvokeAgentToolCommand(
            bearer_token="tok",
            tool=ToolName.SELECT_ROWS,
            args={"schema": "public", "table": "t"},
        )
    )
    assert isinstance(result, Ok)
    assert unwrap(result).status == "error"
    assert bus.events[0].status == "error"
    assert bus.events[0].outcome.reason_code == "database_fault"
