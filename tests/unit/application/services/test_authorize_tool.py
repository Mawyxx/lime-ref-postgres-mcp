"""AuthorizeTool unit tests."""

from __future__ import annotations

from datetime import UTC, datetime

from tests.fakes.policy import FakePolicyStore
from tests.fakes.sql_analyzer import FakeSqlAnalyzer

from lime_ref_postgres_mcp.application.context.request_context import (
    PolicySnapshot,
    RequestContext,
)
from lime_ref_postgres_mcp.application.services.authorize_tool import AuthorizeToolService
from lime_ref_postgres_mcp.domain.access.authorized_agent import AuthorizedAgent
from lime_ref_postgres_mcp.domain.access.capability import ToolCapability
from lime_ref_postgres_mcp.domain.access.policy import PolicyDocument
from lime_ref_postgres_mcp.domain.agent.agent_id import AgentId
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName
from lime_ref_postgres_mcp.domain.common.errors import CapabilityDenied, StatementClassDenied
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, unwrap
from lime_ref_postgres_mcp.domain.sql.analysis import SqlAnalysis
from lime_ref_postgres_mcp.domain.sql.types import SqlStatementClass


def _ctx(
    tool: ToolName,
    *,
    permissions: frozenset[ToolCapability] | None = None,
    args: dict | None = None,
    document: PolicyDocument | None = None,
) -> RequestContext:
    perms = permissions or frozenset(
        {ToolCapability.READ_SCHEMA, ToolCapability.READ_DATA, ToolCapability.WRITE_DATA}
    )
    doc = document or FakePolicyStore().document
    return RequestContext(
        request_id="req-1",
        agent=AuthorizedAgent(
            agent_id=unwrap(AgentId.parse("agent_ok")),
            permissions=perms,
            domain="example.com",
        ),
        tool=tool,
        args=args or {},
        started_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
        policy=PolicySnapshot(document=doc, loaded_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)),
    )


def test_capability_denied() -> None:
    svc = AuthorizeToolService(analyzer=FakeSqlAnalyzer())
    ctx = _ctx(
        ToolName.EXECUTE_WRITE_QUERY,
        permissions=frozenset({ToolCapability.READ_DATA}),
        args={"sql": "INSERT INTO t VALUES (1)"},
    )
    result = svc.execute(ctx)
    assert isinstance(result, Err)
    assert isinstance(result.error, CapabilityDenied)


def test_statement_class_denied_drop() -> None:
    analyzer = FakeSqlAnalyzer()
    analyzer.set_analysis(
        "DROP TABLE t",
        SqlAnalysis(
            statement_class=SqlStatementClass.DDL,
            statement_count=1,
            top_level_kind="DropStmt",
            has_modifying_cte=False,
            has_txn_control=False,
            is_explain_analyze=False,
        ),
    )
    svc = AuthorizeToolService(analyzer=analyzer)
    ctx = _ctx(ToolName.EXECUTE_WRITE_QUERY, args={"sql": "DROP TABLE t"})
    result = svc.execute(ctx)
    assert isinstance(result, Err)
    assert isinstance(result.error, StatementClassDenied)


def test_select_rows_plan() -> None:
    svc = AuthorizeToolService(analyzer=FakeSqlAnalyzer())
    doc = FakePolicyStore().document
    ctx = _ctx(
        ToolName.SELECT_ROWS,
        args={"schema": "public", "table": "t", "limit": 999},
        document=doc,
    )
    result = svc.execute(ctx)
    assert isinstance(result, Ok)
    plan = unwrap(result)
    assert plan.limit == doc.max_rows


def test_missing_sql_on_raw_tool() -> None:
    svc = AuthorizeToolService(analyzer=FakeSqlAnalyzer())
    ctx = _ctx(ToolName.EXECUTE_READONLY_QUERY, args={})
    result = svc.execute(ctx)
    assert isinstance(result, Err)
