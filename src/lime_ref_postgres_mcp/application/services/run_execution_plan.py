"""run_execution_plan — single match site for DatabaseGateway dispatch."""

from __future__ import annotations

from typing import assert_never

from lime_ref_postgres_mcp.application.context.db_payload import DbPayload
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
from lime_ref_postgres_mcp.application.ports.database import DatabaseGateway
from lime_ref_postgres_mcp.domain.common.errors import DatabaseFault
from lime_ref_postgres_mcp.domain.common.result import Result


async def run_execution_plan(
    db: DatabaseGateway, plan: ExecutionPlan
) -> Result[DbPayload, DatabaseFault]:
    if isinstance(plan, ListSchemasPlan):
        return await db.list_schemas()
    if isinstance(plan, ListTablesPlan):
        return await db.list_tables(plan.schema)
    if isinstance(plan, GetTableSchemaPlan):
        return await db.get_table_schema(plan.schema, plan.table)
    if isinstance(plan, SelectRowsPlan):
        return await db.select_rows(plan.schema, plan.table, plan.columns, plan.limit, plan.offset)
    if isinstance(plan, ExecuteReadonlyPlan):
        return await db.execute_readonly(plan.sql, plan.max_rows)
    if isinstance(plan, ExplainPlan):
        return await db.explain(plan.sql)
    if isinstance(plan, ExecuteWritePlan):
        return await db.execute_write(plan.sql, plan.target_table)
    if isinstance(plan, DatabaseStatsPlan):
        return await db.database_stats()
    assert_never(plan)


__all__ = ["run_execution_plan"]
