"""run_execution_plan unit tests."""

from __future__ import annotations

import pytest
from tests.fakes.database import FakeDatabaseGateway

from lime_ref_postgres_mcp.application.context.execution_plan import (
    DatabaseStatsPlan,
    ExecuteReadonlyPlan,
    ExecuteWritePlan,
    ExplainPlan,
    GetTableSchemaPlan,
    ListSchemasPlan,
    ListTablesPlan,
    SelectRowsPlan,
)
from lime_ref_postgres_mcp.application.services.run_execution_plan import run_execution_plan
from lime_ref_postgres_mcp.domain.common.result import Ok, unwrap


@pytest.mark.asyncio
async def test_dispatch_all_plans() -> None:
    db = FakeDatabaseGateway()
    plans = [
        ListSchemasPlan(),
        ListTablesPlan(schema="public"),
        GetTableSchemaPlan(schema="public", table="t"),
        SelectRowsPlan(schema="public", table="t", columns=None, limit=10, offset=0),
        ExecuteReadonlyPlan(sql="SELECT 1", max_rows=10),
        ExplainPlan(sql="SELECT 1"),
        ExecuteWritePlan(sql="INSERT INTO t VALUES (1)", target_table="t"),
        DatabaseStatsPlan(),
    ]
    for plan in plans:
        result = await run_execution_plan(db, plan)
        assert isinstance(result, Ok)
        assert unwrap(result).payload is not None
    assert len(db.calls) == 8
