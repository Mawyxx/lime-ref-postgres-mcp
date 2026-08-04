"""DatabaseGateway port — Postgres tool operations (no asyncpg types)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from lime_ref_postgres_mcp.application.context.db_payload import DbPayload
from lime_ref_postgres_mcp.domain.common.errors import DatabaseFault
from lime_ref_postgres_mcp.domain.common.result import Result


class DatabaseGateway(Protocol):
    async def list_schemas(self) -> Result[DbPayload, DatabaseFault]: ...

    async def list_tables(self, schema: str) -> Result[DbPayload, DatabaseFault]: ...

    async def get_table_schema(
        self, schema: str, table: str
    ) -> Result[DbPayload, DatabaseFault]: ...

    async def select_rows(
        self,
        schema: str,
        table: str,
        columns: Sequence[str] | None,
        limit: int,
        offset: int,
    ) -> Result[DbPayload, DatabaseFault]: ...

    async def execute_readonly(
        self, sql: str, max_rows: int
    ) -> Result[DbPayload, DatabaseFault]: ...

    async def execute_write(
        self, sql: str, target_table: str | None
    ) -> Result[DbPayload, DatabaseFault]: ...

    async def explain(self, sql: str) -> Result[DbPayload, DatabaseFault]: ...

    async def database_stats(self) -> Result[DbPayload, DatabaseFault]: ...


__all__ = ["DatabaseGateway"]
