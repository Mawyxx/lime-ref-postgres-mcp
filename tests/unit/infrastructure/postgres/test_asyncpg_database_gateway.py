"""Unit tests for AsyncpgDatabaseGateway (mocked pool/connection)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest

from lime_ref_postgres_mcp.bootstrap.container import build_scaffold_runtime, create_database
from lime_ref_postgres_mcp.bootstrap.settings import Settings
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, unwrap, unwrap_err
from lime_ref_postgres_mcp.infrastructure.postgres.asyncpg_database_gateway import (
    AsyncpgDatabaseGateway,
    map_asyncpg_fault,
    quote_ident,
)
from lime_ref_postgres_mcp.infrastructure.postgres.result_limits import (
    enforce_byte_limit,
    enforce_row_limit,
    normalize_cell,
    records_to_rows,
)


def _gateway(**kwargs: Any) -> AsyncpgDatabaseGateway:
    defaults = {
        "statement_timeout": "5s",
        "lock_timeout": "2s",
        "idle_in_transaction_timeout": "10s",
        "max_result_bytes": 1_048_576,
    }
    defaults.update(kwargs)
    return AsyncpgDatabaseGateway(**defaults)


def test_u1_quote_ident_rejects_injection() -> None:
    for bad in ('public"; drop', "a-b", "has space", "", "1x"):
        assert isinstance(quote_ident(bad), Err)


def test_u1_quote_ident_accepts() -> None:
    assert unwrap(quote_ident("public")) == '"public"'
    assert unwrap(quote_ident("t_1")) == '"t_1"'


def test_u2_fault_mapper_safe_messages() -> None:
    fault = map_asyncpg_fault(
        asyncpg.exceptions.PostgresConnectionError("dsn=postgresql://user:secret@host/db")
    )
    assert fault.invariant_id == "database.unavailable"
    assert "secret" not in fault.message
    assert "postgresql://" not in fault.message
    assert "SELECT" not in fault.message


def test_map_timeout_and_lock() -> None:
    assert map_asyncpg_fault(asyncpg.exceptions.QueryCanceledError()).invariant_id == (
        "database.timeout"
    )
    assert map_asyncpg_fault(TimeoutError()).invariant_id == "database.timeout"
    assert map_asyncpg_fault(asyncpg.exceptions.LockNotAvailableError()).invariant_id == (
        "database.lock_timeout"
    )
    assert map_asyncpg_fault(RuntimeError("x")).invariant_id == "database.execution_failed"


def test_u3_create_database(settings: Settings) -> None:
    gw = create_database(settings)
    assert isinstance(gw, AsyncpgDatabaseGateway)
    assert gw._pool is None


def test_u4_build_scaffold_runtime_lazy(settings: Settings) -> None:
    runtime = build_scaffold_runtime(settings)
    assert isinstance(runtime.database, AsyncpgDatabaseGateway)
    assert runtime.database._pool is None  # type: ignore[attr-defined]


def test_row_and_byte_limits() -> None:
    assert isinstance(enforce_row_limit(3, 2), Err)
    assert isinstance(enforce_row_limit(2, 2), Ok)
    assert isinstance(enforce_byte_limit({"a": "x" * 100}, 10), Err)
    assert isinstance(enforce_byte_limit({"a": 1}, 1000), Ok)


def test_normalize_and_records() -> None:
    from datetime import date
    from decimal import Decimal
    from uuid import UUID

    assert normalize_cell(Decimal("1.5")) == "1.5"
    assert normalize_cell(date(2020, 1, 1)) == "2020-01-01"
    assert normalize_cell(UUID("00000000-0000-0000-0000-000000000001")).endswith("0001")
    with pytest.raises(TypeError):
        normalize_cell(b"bin")
    with pytest.raises(TypeError):
        normalize_cell(object())
    rec = {"id": 1, "name": "a"}
    rows = unwrap(records_to_rows([rec]))
    assert rows == [{"id": 1, "name": "a"}]


def test_records_to_rows_serialization_fault() -> None:
    class Bad:
        def items(self) -> Any:
            return [("x", object())]

    result = records_to_rows([Bad()])  # type: ignore[list-item]
    assert isinstance(result, Err)
    assert unwrap_err(result).invariant_id == "database.result_serialization_failed"


class _TxnCM:
    def __init__(self) -> None:
        self.readonly: bool | None = None

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args: object) -> None:
        return None


class _AcquireCM:
    def __init__(self, conn: MagicMock) -> None:
        self._conn = conn

    async def __aenter__(self) -> MagicMock:
        return self._conn

    async def __aexit__(self, *args: object) -> None:
        return None


def _mock_pool_conn(
    *,
    fetch: Any = None,
    fetchrow: Any = None,
    execute: str = "INSERT 0 1",
) -> tuple[MagicMock, MagicMock, AsyncpgDatabaseGateway]:
    conn = MagicMock()
    txn = _TxnCM()

    def transaction(*, readonly: bool = False) -> _TxnCM:
        txn.readonly = readonly
        return txn

    conn.transaction = transaction
    conn.execute = AsyncMock(return_value=execute)
    conn.fetch = AsyncMock(return_value=fetch if fetch is not None else [])
    conn.fetchrow = AsyncMock(return_value=fetchrow)
    cursor = MagicMock()
    cursor.fetch = AsyncMock(return_value=fetch if fetch is not None else [])
    conn.cursor = AsyncMock(return_value=cursor)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireCM(conn))
    pool.close = AsyncMock()
    gw = _gateway(pool=pool)
    return pool, conn, gw


@pytest.mark.asyncio
async def test_list_schemas_ok() -> None:
    _, conn, gw = _mock_pool_conn(fetch=[{"nspname": "public"}])
    # fetch returns Record-like; use simple mappings accessed by [0]
    conn.fetch = AsyncMock(return_value=[("public",)])
    result = await gw.list_schemas()
    assert isinstance(result, Ok)
    assert unwrap(result).payload == {"schemas": ["public"]}


@pytest.mark.asyncio
async def test_list_tables_and_schema() -> None:
    _, conn, gw = _mock_pool_conn()
    conn.fetch = AsyncMock(side_effect=[[("t",)], [("id",), ("name",)]])
    tables = await gw.list_tables("public")
    assert unwrap(tables).payload == {"tables": ["t"]}
    schema = await gw.get_table_schema("public", "t")
    assert unwrap(schema).payload == {"columns": ["id", "name"]}


@pytest.mark.asyncio
async def test_select_rows_invalid_ident() -> None:
    _, _, gw = _mock_pool_conn()
    result = await gw.select_rows('public";x', "t", None, 10, 0)
    assert isinstance(result, Err)


@pytest.mark.asyncio
async def test_select_rows_ok_and_columns() -> None:
    _, conn, gw = _mock_pool_conn()
    cursor = MagicMock()
    cursor.fetch = AsyncMock(return_value=[{"id": 1}])
    conn.cursor = AsyncMock(return_value=cursor)
    result = await gw.select_rows("public", "t", ("id",), 10, 0)
    assert unwrap(result).payload == {"rows": [{"id": 1}]}
    sql = conn.cursor.call_args[0][0]
    assert '"id"' in sql and '"public"' in sql and '"t"' in sql


@pytest.mark.asyncio
async def test_execute_readonly_row_limit() -> None:
    _, conn, gw = _mock_pool_conn()
    cursor = MagicMock()
    cursor.fetch = AsyncMock(return_value=[{"a": 1}, {"a": 2}, {"a": 3}])
    conn.cursor = AsyncMock(return_value=cursor)
    result = await gw.execute_readonly("SELECT 1", max_rows=2)
    assert unwrap_err(result).invariant_id == "database.result_row_limit_exceeded"


@pytest.mark.asyncio
async def test_execute_readonly_byte_limit() -> None:
    pool, conn, _ = _mock_pool_conn()
    gw = _gateway(pool=pool, max_result_bytes=5)
    cursor = MagicMock()
    cursor.fetch = AsyncMock(return_value=[{"a": "abcdefghij"}])
    conn.cursor = AsyncMock(return_value=cursor)
    result = await gw.execute_readonly("SELECT 1", max_rows=10)
    assert unwrap_err(result).invariant_id == "database.result_byte_limit_exceeded"


@pytest.mark.asyncio
async def test_execute_write_and_explain_and_stats() -> None:
    pool, conn, gw = _mock_pool_conn(execute="INSERT 0 3")
    write = await gw.execute_write("INSERT INTO t VALUES (1)", None)
    assert unwrap(write).payload == {"ok": True}
    assert unwrap(write).affected_rows == 3

    conn.fetch = AsyncMock(return_value=[("Seq Scan",)])
    plan = await gw.explain("SELECT 1")
    assert "Seq Scan" in unwrap(plan).payload["plan"]

    conn.fetch = AsyncMock(return_value=[("QUERY PLAN",)])
    already = await gw.explain("EXPLAIN SELECT 1")
    assert isinstance(already, Ok)

    conn.fetchrow = AsyncMock(return_value={"size": 42})
    stats = await gw.database_stats()
    assert unwrap(stats).payload == {"size": 42}


@pytest.mark.asyncio
async def test_explain_and_stats_byte_limit() -> None:
    pool, conn, _ = _mock_pool_conn()
    gw = _gateway(pool=pool, max_result_bytes=5)
    conn.fetch = AsyncMock(return_value=[("x" * 100,)])
    assert unwrap_err(await gw.explain("SELECT 1")).invariant_id == (
        "database.result_byte_limit_exceeded"
    )
    conn.fetchrow = AsyncMock(return_value={"size": 1})
    # With max_result_bytes=5, {"size":1} exceeds the byte budget as JSON.
    assert isinstance(await gw.database_stats(), Err)


@pytest.mark.asyncio
async def test_select_rows_star_and_bad_table() -> None:
    pool, conn, gw = _mock_pool_conn()
    cursor = MagicMock()
    cursor.fetch = AsyncMock(return_value=[{"id": 1}])
    conn.cursor = AsyncMock(return_value=cursor)
    ok_rows = await gw.select_rows("public", "t", None, 5, 0)
    assert unwrap(ok_rows).rows_count == 1
    bad = await gw.select_rows("public", "bad-table", None, 1, 0)
    assert isinstance(bad, Err)


@pytest.mark.asyncio
async def test_close_noop_when_unopened() -> None:
    gw = _gateway(pool=None)
    await gw.close()


@pytest.mark.asyncio
async def test_lazy_open_race_second_check(settings: Settings) -> None:
    gw = AsyncpgDatabaseGateway.from_settings(settings)
    fake_pool = MagicMock()
    fake_pool.close = AsyncMock()
    calls = {"n": 0}

    async def slow_create(_settings: Settings) -> MagicMock:
        calls["n"] += 1
        await asyncio.sleep(0.05)
        return fake_pool

    with patch(
        "lime_ref_postgres_mcp.infrastructure.postgres.asyncpg_database_gateway.create_pool",
        new=slow_create,
    ):
        await asyncio.gather(gw.open(), gw.open())
    assert calls["n"] == 1
    await gw.close()


def test_result_limits_extra_branches() -> None:
    from lime_ref_postgres_mcp.infrastructure.postgres.result_limits import payload_utf8_bytes

    assert isinstance(payload_utf8_bytes({"x": object()}), Err)
    assert isinstance(enforce_byte_limit({"x": object()}, 100), Err)
    assert normalize_cell({"a": [1, 2]}) == {"a": [1, 2]}
    with pytest.raises(TypeError):
        normalize_cell(memoryview(b"ab"))


@pytest.mark.asyncio
async def test_map_oserror() -> None:
    assert map_asyncpg_fault(OSError("x")).invariant_id == "database.unavailable"


@pytest.mark.asyncio
async def test_driver_exception_mapped() -> None:
    pool = MagicMock()
    pool.acquire = MagicMock(side_effect=asyncpg.exceptions.PostgresConnectionError("boom"))
    gw = _gateway(pool=pool)
    result = await gw.list_schemas()
    assert unwrap_err(result).invariant_id == "database.unavailable"


@pytest.mark.asyncio
async def test_lazy_open_and_close(settings: Settings) -> None:
    gw = AsyncpgDatabaseGateway.from_settings(settings)
    fake_pool = MagicMock()
    fake_pool.close = AsyncMock()
    with patch(
        "lime_ref_postgres_mcp.infrastructure.postgres.asyncpg_database_gateway.create_pool",
        new=AsyncMock(return_value=fake_pool),
    ) as create:
        await gw.open()
        await gw.open()
        assert create.await_count == 1
        await gw.close()
        fake_pool.close.assert_awaited()
        assert gw._pool is None


@pytest.mark.asyncio
async def test_acquire_pool_without_settings_raises() -> None:
    gw = _gateway(pool=None)
    with pytest.raises(RuntimeError):
        await gw.open()


@pytest.mark.asyncio
async def test_select_rows_bad_column() -> None:
    _, _, gw = _mock_pool_conn()
    result = await gw.select_rows("public", "t", ("bad-col",), 1, 0)
    assert isinstance(result, Err)


@pytest.mark.asyncio
async def test_write_status_without_count() -> None:
    _, conn, gw = _mock_pool_conn(execute="BEGIN")
    result = await gw.execute_write("UPDATE t SET x=1", "t")
    assert unwrap(result).affected_rows is None


@pytest.mark.asyncio
async def test_database_stats_none_row() -> None:
    _, conn, gw = _mock_pool_conn()
    conn.fetchrow = AsyncMock(return_value=None)
    result = await gw.database_stats()
    assert unwrap(result).payload == {"size": 0}


@pytest.mark.asyncio
async def test_read_names_byte_limit() -> None:
    pool, conn, _ = _mock_pool_conn()
    gw = _gateway(pool=pool, max_result_bytes=5)
    conn.fetch = AsyncMock(return_value=[("verylongschemaname",)])
    result = await gw.list_schemas()
    assert unwrap_err(result).invariant_id == "database.result_byte_limit_exceeded"
