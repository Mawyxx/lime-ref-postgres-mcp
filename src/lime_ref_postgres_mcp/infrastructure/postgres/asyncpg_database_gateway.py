"""AsyncpgDatabaseGateway — session guards + single-statement Postgres adapter."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, TypeVar

import asyncpg

from lime_ref_postgres_mcp.application.context.db_payload import DbPayload
from lime_ref_postgres_mcp.bootstrap.observability import log, metrics, monotonic_ms
from lime_ref_postgres_mcp.bootstrap.settings import Settings
from lime_ref_postgres_mcp.domain.common.errors import DatabaseFault
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, Result
from lime_ref_postgres_mcp.infrastructure.postgres.faults import map_asyncpg_fault
from lime_ref_postgres_mcp.infrastructure.postgres.identifiers import quote_ident
from lime_ref_postgres_mcp.infrastructure.postgres.pool import create_pool
from lime_ref_postgres_mcp.infrastructure.postgres.result_limits import (
    enforce_byte_limit,
    enforce_row_limit,
    records_to_rows,
)

_T = TypeVar("_T")

_SQL_LIST_SCHEMAS = """
SELECT nspname FROM pg_catalog.pg_namespace
WHERE nspname NOT LIKE 'pg\\_%' ESCAPE '\\' AND nspname <> 'information_schema'
ORDER BY nspname
"""
_SQL_LIST_TABLES = """
SELECT c.relname FROM pg_catalog.pg_class AS c
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = $1 AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
ORDER BY c.relname
"""
_SQL_TABLE_SCHEMA = """
SELECT a.attname FROM pg_catalog.pg_attribute AS a
JOIN pg_catalog.pg_class AS c ON c.oid = a.attrelid
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = $1 AND c.relname = $2 AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY a.attnum
"""
_SQL_DB_STATS = "SELECT pg_database_size(current_database()) AS size"


class AsyncpgDatabaseGateway:
    def __init__(
        self,
        pool: asyncpg.Pool | None = None,
        *,
        statement_timeout: str,
        lock_timeout: str,
        idle_in_transaction_timeout: str,
        max_result_bytes: int,
        settings: Settings | None = None,
    ) -> None:
        self._pool = pool
        self._statement_timeout = statement_timeout
        self._lock_timeout = lock_timeout
        self._idle_timeout = idle_in_transaction_timeout
        self._max_result_bytes = max_result_bytes
        self._settings = settings
        self._open_lock = asyncio.Lock()

    @classmethod
    def from_settings(cls, settings: Settings) -> AsyncpgDatabaseGateway:
        return cls(
            pool=None,
            statement_timeout=settings.pg_statement_timeout,
            lock_timeout=settings.pg_lock_timeout,
            idle_in_transaction_timeout=settings.pg_idle_in_transaction_timeout,
            max_result_bytes=settings.pg_max_result_bytes,
            settings=settings,
        )

    async def open(self) -> None:
        await self._acquire_pool()

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def list_schemas(self) -> Result[DbPayload, DatabaseFault]:
        return await self._read_names(_SQL_LIST_SCHEMAS, (), "schemas")

    async def list_tables(self, schema: str) -> Result[DbPayload, DatabaseFault]:
        return await self._read_names(_SQL_LIST_TABLES, (schema,), "tables")

    async def get_table_schema(self, schema: str, table: str) -> Result[DbPayload, DatabaseFault]:
        return await self._read_names(_SQL_TABLE_SCHEMA, (schema, table), "columns")

    async def select_rows(
        self,
        schema: str,
        table: str,
        columns: Sequence[str] | None,
        limit: int,
        offset: int,
    ) -> Result[DbPayload, DatabaseFault]:
        built = self._build_select(schema, table, columns)
        if isinstance(built, Err):
            return Err(built.error)
        return await self._read_rows(built.value, (limit, offset), max_rows=limit, op="select_rows")

    async def execute_readonly(self, sql: str, max_rows: int) -> Result[DbPayload, DatabaseFault]:
        return await self._read_rows(sql, (), max_rows=max_rows, op="execute_readonly")

    async def execute_write(
        self, sql: str, target_table: str | None
    ) -> Result[DbPayload, DatabaseFault]:
        _ = target_table

        async def _run(conn: asyncpg.Connection) -> Result[DbPayload, DatabaseFault]:
            status = await conn.execute(sql)
            affected = _parse_affected(status)
            return Ok(DbPayload(payload={"ok": True}, rows_count=None, affected_rows=affected))

        return await self._with_txn(readonly=False, op="execute_write", body=_run)

    async def explain(self, sql: str) -> Result[DbPayload, DatabaseFault]:
        stripped = sql.strip()
        if stripped.casefold().startswith("explain"):
            explain_sql = stripped
        else:
            explain_sql = "EXPLAIN (FORMAT TEXT) " + stripped

        async def _run(conn: asyncpg.Connection) -> Result[DbPayload, DatabaseFault]:
            records = await conn.fetch(explain_sql)
            lines = [str(r[0]) for r in records]
            payload = {"plan": "\n".join(lines)}
            limited = enforce_byte_limit(payload, self._max_result_bytes)
            if isinstance(limited, Err):
                return Err(limited.error)
            return Ok(DbPayload(payload=payload, rows_count=None))

        return await self._with_txn(readonly=True, op="explain", body=_run)

    async def database_stats(self) -> Result[DbPayload, DatabaseFault]:
        async def _run(conn: asyncpg.Connection) -> Result[DbPayload, DatabaseFault]:
            row = await conn.fetchrow(_SQL_DB_STATS)
            size = int(row["size"]) if row is not None else 0
            payload = {"size": size}
            limited = enforce_byte_limit(payload, self._max_result_bytes)
            if isinstance(limited, Err):
                return Err(limited.error)
            return Ok(DbPayload(payload=payload, rows_count=None))

        return await self._with_txn(readonly=True, op="database_stats", body=_run)

    def _build_select(
        self, schema: str, table: str, columns: Sequence[str] | None
    ) -> Result[str, DatabaseFault]:
        q_schema = quote_ident(schema)
        if isinstance(q_schema, Err):
            return Err(q_schema.error)
        q_table = quote_ident(table)
        if isinstance(q_table, Err):
            return Err(q_table.error)
        if columns is None:
            cols_sql = "*"
        else:
            quoted: list[str] = []
            for col in columns:
                q = quote_ident(col)
                if isinstance(q, Err):
                    return Err(q.error)
                quoted.append(q.value)
            cols_sql = ", ".join(quoted)
        sql = (
            "SELECT "  # nosec B608
            + cols_sql
            + " FROM "
            + q_schema.value
            + "."
            + q_table.value
            + " LIMIT $1 OFFSET $2"
        )
        return Ok(sql)

    async def _read_names(
        self, sql: str, args: tuple[Any, ...], key: str
    ) -> Result[DbPayload, DatabaseFault]:
        async def _run(conn: asyncpg.Connection) -> Result[DbPayload, DatabaseFault]:
            records = await conn.fetch(sql, *args)
            names = [str(r[0]) for r in records]
            payload = {key: names}
            limited = enforce_byte_limit(payload, self._max_result_bytes)
            if isinstance(limited, Err):
                return Err(limited.error)
            return Ok(DbPayload(payload=payload, rows_count=len(names)))

        return await self._with_txn(readonly=True, op=key, body=_run)

    async def _read_rows(
        self, sql: str, args: tuple[Any, ...], *, max_rows: int, op: str
    ) -> Result[DbPayload, DatabaseFault]:
        async def _run(conn: asyncpg.Connection) -> Result[DbPayload, DatabaseFault]:
            cursor = await conn.cursor(sql, *args)
            records = await cursor.fetch(max_rows + 1)
            row_check = enforce_row_limit(len(records), max_rows)
            if isinstance(row_check, Err):
                return Err(row_check.error)
            converted = records_to_rows(list(records))
            if isinstance(converted, Err):
                return Err(converted.error)
            payload = {"rows": converted.value}
            byte_check = enforce_byte_limit(payload, self._max_result_bytes)
            if isinstance(byte_check, Err):
                return Err(byte_check.error)
            return Ok(DbPayload(payload=payload, rows_count=len(converted.value)))

        return await self._with_txn(readonly=True, op=op, body=_run)

    async def _with_txn(
        self,
        *,
        readonly: bool,
        op: str,
        body: Callable[[asyncpg.Connection], Awaitable[Result[DbPayload, DatabaseFault]]],
    ) -> Result[DbPayload, DatabaseFault]:
        t0 = monotonic_ms()
        status = "error"
        try:
            pool = await self._acquire_pool()
            async with pool.acquire() as conn:
                async with conn.transaction(readonly=readonly):
                    await self._apply_guards(conn, readonly=readonly)
                    result = await body(conn)
                    status = "ok" if isinstance(result, Ok) else "error"
                    return result
        except Exception as exc:  # noqa: BLE001 — map all driver/OS faults
            status = "error"
            return Err(map_asyncpg_fault(exc))
        finally:
            duration_ms = int(monotonic_ms() - t0)
            log(
                "db",
                "db.op",
                op=op,
                status=status,
                duration_ms=duration_ms,
                readonly=readonly,
            )
            metrics.inc("mcp_db_op_total", op=op, status=status)
            metrics.observe_ms("mcp_db_op_duration_ms", float(duration_ms), op=op)

    async def _apply_guards(self, conn: asyncpg.Connection, *, readonly: bool) -> None:
        await conn.execute(
            "SELECT set_config('statement_timeout', $1, true),"
            " set_config('lock_timeout', $2, true),"
            " set_config('idle_in_transaction_session_timeout', $3, true)",
            self._statement_timeout,
            self._lock_timeout,
            self._idle_timeout,
        )
        if readonly:
            await conn.execute("SELECT set_config('transaction_read_only', 'on', true)")

    async def _acquire_pool(self) -> asyncpg.Pool:
        if self._pool is not None:
            return self._pool
        async with self._open_lock:
            if self._pool is not None:
                return self._pool
            if self._settings is None:
                raise RuntimeError("AsyncpgDatabaseGateway has no pool and no settings")
            self._pool = await create_pool(self._settings)
            log("db", "pool.open", status="ok", mode="lazy")
            return self._pool


def _parse_affected(status: str) -> int | None:
    parts = status.split()
    if len(parts) >= 2 and parts[-1].isdigit():
        return int(parts[-1])
    return None


__all__ = ["AsyncpgDatabaseGateway", "map_asyncpg_fault", "quote_ident"]
