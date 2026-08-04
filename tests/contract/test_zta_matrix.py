"""ZTA matrix Z1–Z10 (TDD §14.1) — Invoke path contract tests."""

from __future__ import annotations

import dataclasses

import pytest
from tests.fakes.identity import FakePassportVerifier
from tests.fakes.policy import FakePolicyStore, read_only_policy, write_policy
from tests.support.build_test_runtime import wire_invoke

from lime_ref_postgres_mcp.application.commands.invoke_agent_tool import InvokeAgentToolCommand
from lime_ref_postgres_mcp.application.ports.identity import PassportClaims
from lime_ref_postgres_mcp.domain.agent.agent_id import AgentId
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName
from lime_ref_postgres_mcp.domain.common.errors import (
    AgentNotAllowlisted,
    PassportInvalid,
    PassportMissing,
)
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, unwrap
from lime_ref_postgres_mcp.infrastructure.sql.pglast_sql_analyzer import PglastSqlAnalyzer

FORBIDDEN_EVENT_KEYS = frozenset({"response", "payload", "rows", "result", "body"})


def _assert_no_payload_leak(event: object) -> None:
    as_dict = dataclasses.asdict(event)  # type: ignore[arg-type]
    flat_keys = set(as_dict.keys()) | set(as_dict.get("request", {}).keys())
    assert FORBIDDEN_EVENT_KEYS.isdisjoint(flat_keys)
    outcome = as_dict.get("outcome") or {}
    assert "rows" not in outcome
    assert outcome.get("rows_count") is None or isinstance(outcome.get("rows_count"), int)


@pytest.mark.asyncio
async def test_z1_no_bearer() -> None:
    invoke, bus = wire_invoke()
    result = await invoke.execute(
        InvokeAgentToolCommand(bearer_token=None, tool=ToolName.LIST_SCHEMAS, args={})
    )
    assert isinstance(result, Err)
    assert isinstance(result.error, PassportMissing)
    assert bus.events == []


@pytest.mark.asyncio
async def test_z1_bad_jwt() -> None:
    invoke, bus = wire_invoke()
    result = await invoke.execute(
        InvokeAgentToolCommand(bearer_token="bad", tool=ToolName.LIST_SCHEMAS, args={})
    )
    assert isinstance(result, Err)
    assert isinstance(result.error, PassportInvalid)
    assert bus.events == []


@pytest.mark.asyncio
async def test_z2_not_in_whitelist() -> None:
    verifier = FakePassportVerifier()
    verifier.register(
        "tok",
        PassportClaims(agent_id=unwrap(AgentId.parse("stranger")), domain="example.com"),
    )
    invoke, bus = wire_invoke(verifier=verifier)
    result = await invoke.execute(
        InvokeAgentToolCommand(bearer_token="tok", tool=ToolName.LIST_SCHEMAS, args={})
    )
    assert isinstance(result, Err)
    assert isinstance(result.error, AgentNotAllowlisted)
    assert bus.events == []


@pytest.mark.asyncio
async def test_z3_write_without_capability() -> None:
    invoke, bus = wire_invoke(
        policy_store=FakePolicyStore(read_only_policy()),
        analyzer=PglastSqlAnalyzer(),
    )
    result = await invoke.execute(
        InvokeAgentToolCommand(
            bearer_token="tok",
            tool=ToolName.EXECUTE_WRITE_QUERY,
            args={"sql": "INSERT INTO t VALUES (1)"},
        )
    )
    assert isinstance(result, Ok)
    assert unwrap(result).status == "denied"
    assert bus.events[0].outcome.reason_code == "capability_denied"


@pytest.mark.asyncio
async def test_z4_drop_via_write() -> None:
    invoke, bus = wire_invoke(
        policy_store=FakePolicyStore(write_policy()),
        analyzer=PglastSqlAnalyzer(),
    )
    result = await invoke.execute(
        InvokeAgentToolCommand(
            bearer_token="tok",
            tool=ToolName.EXECUTE_WRITE_QUERY,
            args={"sql": "DROP TABLE t"},
        )
    )
    assert isinstance(result, Ok)
    assert unwrap(result).status == "denied"
    assert bus.events[0].outcome.reason_code == "statement_class_denied"
    assert bus.events[0].outcome.statement_class == "DDL"


@pytest.mark.asyncio
async def test_z5_select_rows_ok_no_rows_in_event() -> None:
    invoke, bus = wire_invoke(policy_store=FakePolicyStore(read_only_policy()))
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
    event = bus.events[0]
    assert event.status == "ok"
    assert event.outcome.rows_count == 1
    _assert_no_payload_leak(event)
    assert not isinstance(event.outcome.rows_count, list)


@pytest.mark.asyncio
async def test_z6_insert_ok() -> None:
    invoke, bus = wire_invoke(
        policy_store=FakePolicyStore(write_policy()),
        analyzer=PglastSqlAnalyzer(),
    )
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


@pytest.mark.asyncio
async def test_z7_stats_without_admin() -> None:
    invoke, bus = wire_invoke(policy_store=FakePolicyStore(read_only_policy()))
    result = await invoke.execute(
        InvokeAgentToolCommand(bearer_token="tok", tool=ToolName.GET_DATABASE_STATS, args={})
    )
    assert isinstance(result, Ok)
    assert unwrap(result).status == "denied"
    assert bus.events[0].outcome.reason_code == "capability_denied"


@pytest.mark.asyncio
async def test_z8_cte_delete_readonly() -> None:
    invoke, bus = wire_invoke(
        policy_store=FakePolicyStore(read_only_policy()),
        analyzer=PglastSqlAnalyzer(),
    )
    result = await invoke.execute(
        InvokeAgentToolCommand(
            bearer_token="tok",
            tool=ToolName.EXECUTE_READONLY_QUERY,
            args={"sql": "WITH x AS (DELETE FROM t RETURNING *) SELECT * FROM x"},
        )
    )
    assert isinstance(result, Ok)
    assert unwrap(result).status == "denied"
    assert bus.events[0].status == "denied"


@pytest.mark.asyncio
async def test_z9_multi_stmt() -> None:
    invoke, bus = wire_invoke(
        policy_store=FakePolicyStore(read_only_policy()),
        analyzer=PglastSqlAnalyzer(),
    )
    result = await invoke.execute(
        InvokeAgentToolCommand(
            bearer_token="tok",
            tool=ToolName.EXECUTE_READONLY_QUERY,
            args={"sql": "COMMIT; DROP SCHEMA public CASCADE"},
        )
    )
    assert isinstance(result, Ok)
    assert unwrap(result).status == "denied"
    assert bus.events[0].status == "denied"


@pytest.mark.asyncio
async def test_z10_modifying_cte_on_write() -> None:
    invoke, bus = wire_invoke(
        policy_store=FakePolicyStore(write_policy()),
        analyzer=PglastSqlAnalyzer(),
    )
    result = await invoke.execute(
        InvokeAgentToolCommand(
            bearer_token="tok",
            tool=ToolName.EXECUTE_WRITE_QUERY,
            args={"sql": "WITH x AS (INSERT INTO logs VALUES (1) RETURNING *) SELECT * FROM x"},
        )
    )
    assert isinstance(result, Ok)
    assert unwrap(result).status == "denied"
    assert bus.events[0].status == "denied"
