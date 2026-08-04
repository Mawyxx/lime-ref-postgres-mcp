"""AuthorizeTool — remaining tool plan / input branches."""

from __future__ import annotations

from datetime import UTC, datetime

from tests.fakes.policy import FakePolicyStore
from tests.fakes.sql_analyzer import FakeSqlAnalyzer

from lime_ref_postgres_mcp.application.context.execution_plan import (
    DatabaseStatsPlan,
    ExecuteReadonlyPlan,
    ExecuteWritePlan,
    ExplainPlan,
    GetTableSchemaPlan,
    ListSchemasPlan,
    ListTablesPlan,
)
from lime_ref_postgres_mcp.application.context.request_context import (
    PolicySnapshot,
    RequestContext,
)
from lime_ref_postgres_mcp.application.services.authorize_tool import AuthorizeToolService
from lime_ref_postgres_mcp.domain.access.authorized_agent import AuthorizedAgent
from lime_ref_postgres_mcp.domain.access.capability import ToolCapability
from lime_ref_postgres_mcp.domain.agent.agent_id import AgentId
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName
from lime_ref_postgres_mcp.domain.common.errors import SqlParseFault, ToolInputInvalid
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, unwrap
from lime_ref_postgres_mcp.domain.sql.analysis import SqlAnalysis
from lime_ref_postgres_mcp.domain.sql.types import SqlStatementClass


def _ctx(tool: ToolName, args: dict | None = None) -> RequestContext:
    doc = FakePolicyStore().document
    return RequestContext(
        request_id="req-1",
        agent=AuthorizedAgent(
            agent_id=unwrap(AgentId.parse("agent_ok")),
            permissions=frozenset(ToolCapability),
            domain="example.com",
        ),
        tool=tool,
        args=args or {},
        started_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
        policy=PolicySnapshot(document=doc, loaded_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)),
    )


def test_list_schemas_plan() -> None:
    result = AuthorizeToolService(FakeSqlAnalyzer()).execute(_ctx(ToolName.LIST_SCHEMAS))
    assert isinstance(unwrap(result), ListSchemasPlan)


def test_list_tables_and_schema() -> None:
    svc = AuthorizeToolService(FakeSqlAnalyzer())
    tables = unwrap(svc.execute(_ctx(ToolName.LIST_TABLES, {"schema": "public"})))
    assert isinstance(tables, ListTablesPlan)
    schema = unwrap(
        svc.execute(_ctx(ToolName.GET_TABLE_SCHEMA, {"schema": "public", "table": "t"}))
    )
    assert isinstance(schema, GetTableSchemaPlan)


def test_list_tables_missing_schema() -> None:
    result = AuthorizeToolService(FakeSqlAnalyzer()).execute(_ctx(ToolName.LIST_TABLES, {}))
    assert isinstance(result, Err)
    assert isinstance(result.error, ToolInputInvalid)


def test_get_table_schema_missing_table() -> None:
    result = AuthorizeToolService(FakeSqlAnalyzer()).execute(
        _ctx(ToolName.GET_TABLE_SCHEMA, {"schema": "public"})
    )
    assert isinstance(result, Err)


def test_select_rows_bad_columns() -> None:
    result = AuthorizeToolService(FakeSqlAnalyzer()).execute(
        _ctx(
            ToolName.SELECT_ROWS,
            {"schema": "public", "table": "t", "columns": [1]},
        )
    )
    assert isinstance(result, Err)


def test_select_rows_with_columns() -> None:
    result = AuthorizeToolService(FakeSqlAnalyzer()).execute(
        _ctx(
            ToolName.SELECT_ROWS,
            {"schema": "public", "table": "t", "columns": ["id"], "offset": 2},
        )
    )
    assert isinstance(result, Ok)
    assert unwrap(result).columns == ("id",)
    assert unwrap(result).offset == 2


def test_readonly_and_explain_and_write() -> None:
    analyzer = FakeSqlAnalyzer()
    analyzer.set_analysis(
        "SELECT 1",
        SqlAnalysis(
            statement_class=SqlStatementClass.READ,
            statement_count=1,
            top_level_kind="SelectStmt",
            has_modifying_cte=False,
            has_txn_control=False,
            is_explain_analyze=False,
        ),
    )
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
    svc = AuthorizeToolService(analyzer)
    ro = unwrap(svc.execute(_ctx(ToolName.EXECUTE_READONLY_QUERY, {"sql": "SELECT 1"})))
    assert isinstance(ro, ExecuteReadonlyPlan)
    ex = unwrap(svc.execute(_ctx(ToolName.EXPLAIN_QUERY_PLAN, {"sql": "SELECT 1"})))
    assert isinstance(ex, ExplainPlan)
    wr = unwrap(
        svc.execute(
            _ctx(
                ToolName.EXECUTE_WRITE_QUERY,
                {"sql": "INSERT INTO t VALUES (1)", "target_table": " t "},
            )
        )
    )
    assert isinstance(wr, ExecuteWritePlan)
    assert wr.target_table == "t"


def test_database_stats_plan() -> None:
    result = AuthorizeToolService(FakeSqlAnalyzer()).execute(_ctx(ToolName.GET_DATABASE_STATS))
    assert isinstance(unwrap(result), DatabaseStatsPlan)


def test_sql_parse_fault() -> None:
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
    result = AuthorizeToolService(analyzer).execute(
        _ctx(ToolName.EXECUTE_READONLY_QUERY, {"sql": "SELEC 1"})
    )
    assert isinstance(result, Err)
    assert isinstance(result.error, SqlParseFault)


def test_explain_missing_sql() -> None:
    result = AuthorizeToolService(FakeSqlAnalyzer()).execute(_ctx(ToolName.EXPLAIN_QUERY_PLAN, {}))
    assert isinstance(result, Err)


def test_get_table_schema_missing_schema() -> None:
    result = AuthorizeToolService(FakeSqlAnalyzer()).execute(
        _ctx(ToolName.GET_TABLE_SCHEMA, {"table": "t"})
    )
    assert isinstance(result, Err)


def test_select_rows_missing_schema_or_table() -> None:
    svc = AuthorizeToolService(FakeSqlAnalyzer())
    assert isinstance(svc.execute(_ctx(ToolName.SELECT_ROWS, {"table": "t"})), Err)
    assert isinstance(svc.execute(_ctx(ToolName.SELECT_ROWS, {"schema": "public"})), Err)


def test_write_without_target_table() -> None:
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
    result = AuthorizeToolService(analyzer).execute(
        _ctx(ToolName.EXECUTE_WRITE_QUERY, {"sql": "INSERT INTO t VALUES (1)"})
    )
    assert isinstance(result, Ok)
    assert unwrap(result).target_table is None
