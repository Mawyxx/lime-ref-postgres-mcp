"""InvokeAgentToolService orchestration tests."""

from __future__ import annotations

import pytest
from tests.fakes.policy import FakePolicyStore, read_only_policy
from tests.fakes.sql_analyzer import FakeSqlAnalyzer
from tests.support.build_test_runtime import wire_invoke

from lime_ref_postgres_mcp.application.commands.invoke_agent_tool import InvokeAgentToolCommand
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName
from lime_ref_postgres_mcp.domain.common.errors import PassportMissing
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, unwrap
from lime_ref_postgres_mcp.domain.sql.analysis import SqlAnalysis
from lime_ref_postgres_mcp.domain.sql.types import SqlStatementClass


@pytest.mark.asyncio
async def test_preauth_no_emit() -> None:
    invoke, bus = wire_invoke()
    result = await invoke.execute(
        InvokeAgentToolCommand(bearer_token=None, tool=ToolName.LIST_SCHEMAS, args={})
    )
    assert isinstance(result, Err)
    assert isinstance(result.error, PassportMissing)
    assert bus.events == []


@pytest.mark.asyncio
async def test_capability_deny_emits_and_returns_ok_reply() -> None:
    invoke, bus = wire_invoke(policy_store=FakePolicyStore(read_only_policy()))
    result = await invoke.execute(
        InvokeAgentToolCommand(
            bearer_token="tok",
            tool=ToolName.EXECUTE_WRITE_QUERY,
            args={"sql": "INSERT INTO t VALUES (1)"},
        )
    )
    assert isinstance(result, Ok)
    reply = unwrap(result)
    assert reply.status == "denied"
    assert len(bus.events) == 1
    assert bus.events[0].status == "denied"
    assert bus.events[0].outcome.reason_code == "capability_denied"


@pytest.mark.asyncio
async def test_happy_select_rows() -> None:
    invoke, bus = wire_invoke()
    result = await invoke.execute(
        InvokeAgentToolCommand(
            bearer_token="tok",
            tool=ToolName.SELECT_ROWS,
            args={"schema": "public", "table": "t"},
        )
    )
    assert isinstance(result, Ok)
    reply = unwrap(result)
    assert reply.status == "ok"
    assert "rows" in reply.payload
    assert len(bus.events) == 1
    assert bus.events[0].outcome.rows_count == 1
    assert "rows" not in bus.events[0].request


@pytest.mark.asyncio
async def test_write_insert_ok_with_fake_analyzer() -> None:
    analyzer = FakeSqlAnalyzer()
    analyzer.set_analysis(
        "INSERT INTO t VALUES (1)",
        SqlAnalysis(
            statement_class=SqlStatementClass.DML,
            statement_count=1,
            top_level_kind="InsertStmt",
            has_modifying_cte=False,
            has_txn_control=False,
            is_explain_analyze=False,
        ),
    )
    invoke, bus = wire_invoke(analyzer=analyzer)
    result = await invoke.execute(
        InvokeAgentToolCommand(
            bearer_token="tok",
            tool=ToolName.EXECUTE_WRITE_QUERY,
            args={"sql": "INSERT INTO t VALUES (1)"},
        )
    )
    assert isinstance(result, Ok)
    assert unwrap(result).status == "ok"
    assert bus.events[0].status == "ok"
