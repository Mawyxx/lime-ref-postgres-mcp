"""AuthorizeTool — capability + SQL guard → ExecutionPlan."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, assert_never

from lime_ref_postgres_mcp.application.context.execution_plan import (
    DatabaseStatsPlan,
    ExecuteReadonlyPlan,
    ExecuteWritePlan,
    ExecutionPlan,
    ExplainPlan,
    GetTableSchemaPlan,
    ListSchemasPlan,
    ListTablesPlan,
    SelectRowsPlan,
)
from lime_ref_postgres_mcp.application.context.request_context import RequestContext
from lime_ref_postgres_mcp.application.ports.sql_analyzer import SqlAnalyzer
from lime_ref_postgres_mcp.bootstrap.observability import log, metrics
from lime_ref_postgres_mcp.domain.access.capability_check import capability_check
from lime_ref_postgres_mcp.domain.access.policy import REASON_TOOL_INPUT_INVALID, PolicyDocument
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import RAW_SQL_TOOLS, ToolName
from lime_ref_postgres_mcp.domain.common.errors import (
    CapabilityDenied,
    SqlParseFault,
    StatementClassDenied,
    ToolInputInvalid,
)
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, Result
from lime_ref_postgres_mcp.domain.sql.guard import guard

AuthzError = CapabilityDenied | StatementClassDenied | SqlParseFault | ToolInputInvalid


def _input_invalid(message: str, **context: Any) -> Err[ToolInputInvalid]:
    return Err(
        ToolInputInvalid(
            invariant_id="tool.input_invalid",
            message=message,
            context={**context, "reason_code": REASON_TOOL_INPUT_INVALID},
        )
    )


def _require_str(args: Mapping[str, Any], key: str) -> Result[str, ToolInputInvalid]:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        return _input_invalid(f"missing or invalid '{key}'", field=key)
    return Ok(value.strip())


def _raw_sql(args: Mapping[str, Any]) -> str:
    return str(args["sql"]).strip()


def _plan_list_tables(args: Mapping[str, Any]) -> Result[ExecutionPlan, ToolInputInvalid]:
    schema = _require_str(args, "schema")
    if isinstance(schema, Err):
        return Err(schema.error)
    return Ok(ListTablesPlan(schema=schema.value))


def _plan_get_table_schema(args: Mapping[str, Any]) -> Result[ExecutionPlan, ToolInputInvalid]:
    schema = _require_str(args, "schema")
    if isinstance(schema, Err):
        return Err(schema.error)
    table = _require_str(args, "table")
    if isinstance(table, Err):
        return Err(table.error)
    return Ok(GetTableSchemaPlan(schema=schema.value, table=table.value))


def _plan_select_rows(
    args: Mapping[str, Any], doc: PolicyDocument
) -> Result[ExecutionPlan, ToolInputInvalid]:
    schema = _require_str(args, "schema")
    if isinstance(schema, Err):
        return Err(schema.error)
    table = _require_str(args, "table")
    if isinstance(table, Err):
        return Err(table.error)
    raw_limit = args.get("limit")
    limit = doc.clamp_limit(raw_limit if isinstance(raw_limit, int) else None)
    raw_offset = args.get("offset")
    offset = raw_offset if isinstance(raw_offset, int) and raw_offset >= 0 else 0
    columns = args.get("columns")
    cols: tuple[str, ...] | None = None
    if columns is not None:
        if not isinstance(columns, (list, tuple)) or not all(isinstance(c, str) for c in columns):
            return _input_invalid("columns must be a list of strings", field="columns")
        cols = tuple(columns)
    return Ok(
        SelectRowsPlan(
            schema=schema.value,
            table=table.value,
            columns=cols,
            limit=limit,
            offset=offset,
        )
    )


def _plan_raw_sql(tool: ToolName, args: Mapping[str, Any], doc: PolicyDocument) -> ExecutionPlan:
    sql = _raw_sql(args)
    if tool is ToolName.EXECUTE_READONLY_QUERY:
        raw_limit = args.get("limit")
        max_rows = doc.clamp_limit(raw_limit if isinstance(raw_limit, int) else None)
        return ExecuteReadonlyPlan(sql=sql, max_rows=max_rows)
    if tool is ToolName.EXPLAIN_QUERY_PLAN:
        return ExplainPlan(sql=sql)
    target = args.get("target_table")
    target_table = target.strip() if isinstance(target, str) and target.strip() else None
    return ExecuteWritePlan(sql=sql, target_table=target_table)


def _build_plan(ctx: RequestContext) -> Result[ExecutionPlan, ToolInputInvalid]:
    args = ctx.args
    tool = ctx.tool
    doc = ctx.policy.document
    if tool is ToolName.LIST_SCHEMAS:
        return Ok(ListSchemasPlan())
    if tool is ToolName.LIST_TABLES:
        return _plan_list_tables(args)
    if tool is ToolName.GET_TABLE_SCHEMA:
        return _plan_get_table_schema(args)
    if tool is ToolName.SELECT_ROWS:
        return _plan_select_rows(args, doc)
    if tool is ToolName.EXECUTE_READONLY_QUERY:
        return Ok(_plan_raw_sql(tool, args, doc))
    if tool is ToolName.EXPLAIN_QUERY_PLAN:
        return Ok(_plan_raw_sql(tool, args, doc))
    if tool is ToolName.EXECUTE_WRITE_QUERY:
        return Ok(_plan_raw_sql(tool, args, doc))
    if tool is ToolName.GET_DATABASE_STATS:
        return Ok(DatabaseStatsPlan())
    assert_never(tool)


@dataclass(frozen=True, slots=True)
class AuthorizeToolService:
    analyzer: SqlAnalyzer

    def execute(self, ctx: RequestContext) -> Result[ExecutionPlan, AuthzError]:
        result = self._authorize(ctx)
        tool = ctx.tool.value
        if isinstance(result, Err):
            err = result.error
            code = str(err.context.get("reason_code") or err.invariant_id)
            log(
                "authorize",
                "authorize.deny",
                level="WARNING",
                tool=tool,
                code=code,
                invariant_id=err.invariant_id,
            )
            metrics.inc("mcp_authorize_deny_total", tool=tool, code=code)
        else:
            log("authorize", "authorize.allow", tool=tool)
        return result

    def _authorize(self, ctx: RequestContext) -> Result[ExecutionPlan, AuthzError]:
        cap = capability_check(ctx.tool, ctx.agent.permissions)
        if not cap.allowed:
            denied = cap.to_denied_error()
            assert denied is not None
            return Err(denied)
        if ctx.tool in RAW_SQL_TOOLS:
            sql = ctx.args.get("sql")
            if not isinstance(sql, str) or not sql.strip():
                return _input_invalid("missing or invalid 'sql'", field="sql")
            analyzed = self.analyzer.analyze(sql)
            if isinstance(analyzed, Err):
                return Err(analyzed.error)
            decision = guard(ctx.tool, analyzed.value, ctx.agent.permissions)
            if not decision.allowed:
                stmt_denied = decision.to_denied_error()
                assert stmt_denied is not None
                return Err(stmt_denied)
        return _build_plan(ctx)


__all__ = ["AuthzError", "AuthorizeToolService", "_build_plan"]
