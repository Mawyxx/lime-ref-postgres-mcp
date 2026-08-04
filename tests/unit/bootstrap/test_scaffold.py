"""Scaffold fail-closed adapters."""

from __future__ import annotations

import pytest

from lime_ref_postgres_mcp.bootstrap.scaffold import (
    ScaffoldRejectVerifier,
    ScaffoldUnavailableDatabase,
    ScaffoldUnavailablePolicyStore,
)
from lime_ref_postgres_mcp.domain.common.errors import (
    DatabaseFault,
    PassportInvalid,
    PolicyStoreFault,
)
from lime_ref_postgres_mcp.domain.common.result import Err


@pytest.mark.asyncio
async def test_scaffold_verifier_rejects() -> None:
    result = await ScaffoldRejectVerifier().verify("any")
    assert isinstance(result, Err)
    assert isinstance(result.error, PassportInvalid)


@pytest.mark.asyncio
async def test_scaffold_policy_faults() -> None:
    result = await ScaffoldUnavailablePolicyStore().current()
    assert isinstance(result, Err)
    assert isinstance(result.error, PolicyStoreFault)


@pytest.mark.asyncio
async def test_scaffold_database_faults() -> None:
    db = ScaffoldUnavailableDatabase()
    results = [
        await db.list_schemas(),
        await db.list_tables("public"),
        await db.get_table_schema("public", "t"),
        await db.select_rows("public", "t", None, 10, 0),
        await db.execute_readonly("SELECT 1", 10),
        await db.execute_write("INSERT INTO t VALUES (1)", "t"),
        await db.explain("SELECT 1"),
        await db.database_stats(),
    ]
    for result in results:
        assert isinstance(result, Err)
        assert isinstance(result.error, DatabaseFault)
