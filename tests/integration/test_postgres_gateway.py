"""G-1..G-11 — AsyncpgDatabaseGateway against real Postgres (Testcontainers)."""

from __future__ import annotations

import asyncpg
import pytest

from lime_ref_postgres_mcp.domain.common.result import Err, Ok, unwrap, unwrap_err
from lime_ref_postgres_mcp.infrastructure.postgres.asyncpg_database_gateway import (
    AsyncpgDatabaseGateway,
)

pytestmark = pytest.mark.integration


async def _seed(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS public.lime_p4_items ("
            "id int PRIMARY KEY, name text NOT NULL, blob text)"
        )
        await conn.execute("TRUNCATE public.lime_p4_items")
        await conn.execute("INSERT INTO public.lime_p4_items (id, name, blob) VALUES (1, 'a', 'x')")


@pytest.mark.asyncio
async def test_g1_list_schemas(database: AsyncpgDatabaseGateway) -> None:
    result = await database.list_schemas()
    assert isinstance(result, Ok)
    assert "public" in unwrap(result).payload["schemas"]


@pytest.mark.asyncio
async def test_g2_tables_schema_select(database: AsyncpgDatabaseGateway) -> None:
    assert database._pool is not None
    await _seed(database._pool)
    tables = await database.list_tables("public")
    assert "lime_p4_items" in unwrap(tables).payload["tables"]
    schema = await database.get_table_schema("public", "lime_p4_items")
    cols = unwrap(schema).payload["columns"]
    assert "id" in cols and "name" in cols
    rows = await database.select_rows("public", "lime_p4_items", None, 10, 0)
    assert unwrap(rows).rows_count == 1
    assert unwrap(rows).payload["rows"][0]["id"] == 1


@pytest.mark.asyncio
async def test_g3_execute_readonly(database: AsyncpgDatabaseGateway) -> None:
    result = await database.execute_readonly("SELECT 1 AS n", max_rows=10)
    assert unwrap(result).payload["rows"][0]["n"] == 1
    assert unwrap(result).rows_count == 1


@pytest.mark.asyncio
async def test_g4_execute_write_roundtrip(database: AsyncpgDatabaseGateway) -> None:
    assert database._pool is not None
    await _seed(database._pool)
    write = await database.execute_write(
        "INSERT INTO public.lime_p4_items (id, name, blob) VALUES (2, 'b', 'y')",
        "lime_p4_items",
    )
    assert unwrap(write).payload == {"ok": True}
    rows = await database.select_rows("public", "lime_p4_items", None, 10, 0)
    ids = {r["id"] for r in unwrap(rows).payload["rows"]}
    assert ids == {1, 2}


@pytest.mark.asyncio
async def test_g5_statement_timeout(database: AsyncpgDatabaseGateway) -> None:
    gw = AsyncpgDatabaseGateway(
        database._pool,
        statement_timeout="1s",
        lock_timeout="1s",
        idle_in_transaction_timeout="5s",
        max_result_bytes=1_048_576,
    )
    result = await gw.execute_readonly("SELECT pg_sleep(30)", max_rows=1)
    assert isinstance(result, Err)
    assert unwrap_err(result).invariant_id in {
        "database.timeout",
        "database.execution_failed",
    }


@pytest.mark.asyncio
async def test_g6_max_rows(database: AsyncpgDatabaseGateway) -> None:
    result = await database.execute_readonly("SELECT generate_series(1, 5) AS n", max_rows=2)
    assert unwrap_err(result).invariant_id == "database.result_row_limit_exceeded"


@pytest.mark.asyncio
async def test_g7_max_result_bytes(database: AsyncpgDatabaseGateway) -> None:
    tiny = AsyncpgDatabaseGateway(
        database._pool,
        statement_timeout="5s",
        lock_timeout="2s",
        idle_in_transaction_timeout="10s",
        max_result_bytes=20,
    )
    result = await tiny.execute_readonly("SELECT repeat('z', 200) AS blob", max_rows=10)
    assert unwrap_err(result).invariant_id == "database.result_byte_limit_exceeded"


@pytest.mark.asyncio
async def test_g8_invalid_identifier(database: AsyncpgDatabaseGateway) -> None:
    result = await database.select_rows('public";drop', "t", None, 1, 0)
    assert isinstance(result, Err)
    assert unwrap_err(result).invariant_id == "database.execution_failed"


@pytest.mark.asyncio
async def test_g9_explain(database: AsyncpgDatabaseGateway) -> None:
    result = await database.explain("SELECT 1")
    assert isinstance(result, Ok)
    assert isinstance(unwrap(result).payload["plan"], str)
    assert len(unwrap(result).payload["plan"]) > 0


@pytest.mark.asyncio
async def test_g10_connection_refused_safe_message() -> None:
    from pathlib import Path

    from lime_ref_postgres_mcp.bootstrap.settings import Settings

    settings = Settings(
        lime_expected_domain="example.com",
        lime_jwks_url="https://lime.pics/.well-known/jwks.json",
        lime_expected_aud="mcp",
        lime_jwks_cache_ttl_seconds=3600,
        lime_jwt_leeway_seconds=120,
        agents_policy_path=Path("."),
        policy_reload_ttl_seconds=60,
        postgres_url="postgresql://nobody:nopass@127.0.0.1:1/none",
        pg_statement_timeout="5s",
        pg_lock_timeout="2s",
        pg_idle_in_transaction_timeout="10s",
        pg_max_result_bytes=1024,
        pg_pool_min_size=1,
        pg_pool_max_size=1,
        enable_console_event_sink=False,
        log_level="INFO",
        log_format="json",
        log_stream="stderr",
        metrics_enabled=True,
        mcp_bind_host="127.0.0.1",
        mcp_port=8000,
    )
    gw = AsyncpgDatabaseGateway.from_settings(settings)
    result = await gw.list_schemas()
    assert isinstance(result, Err)
    msg = unwrap_err(result).message
    assert "nopass" not in msg
    assert "127.0.0.1" not in msg
    assert unwrap_err(result).invariant_id == "database.unavailable"


@pytest.mark.asyncio
async def test_g11_readonly_rejects_dml(database: AsyncpgDatabaseGateway) -> None:
    assert database._pool is not None
    await _seed(database._pool)
    result = await database.execute_readonly(
        "INSERT INTO public.lime_p4_items (id, name, blob) VALUES (99, 'z', 'z')",
        max_rows=1,
    )
    assert isinstance(result, Err)
    assert unwrap_err(result).invariant_id in {
        "database.execution_failed",
        "database.unavailable",
    }


@pytest.mark.asyncio
async def test_g_database_stats(database: AsyncpgDatabaseGateway) -> None:
    result = await database.database_stats()
    assert unwrap(result).payload["size"] > 0
