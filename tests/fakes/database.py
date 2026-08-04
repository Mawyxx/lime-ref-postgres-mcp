"""Fake DatabaseGateway."""

from __future__ import annotations

from collections.abc import Sequence

from lime_ref_postgres_mcp.application.context.db_payload import DbPayload
from lime_ref_postgres_mcp.domain.common.errors import DatabaseFault
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, Result


class FakeDatabaseGateway:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.select_payload = DbPayload(
            payload={"rows": [{"id": 1}]}, rows_count=1, affected_rows=None
        )
        self.write_payload = DbPayload(payload={"ok": True}, rows_count=None, affected_rows=1)
        self.fault: DatabaseFault | None = None

    def _maybe_fault(self, name: str) -> Result[DbPayload, DatabaseFault] | None:
        self.calls.append(name)
        if self.fault is not None:
            return Err(self.fault)
        return None

    async def list_schemas(self) -> Result[DbPayload, DatabaseFault]:
        fault = self._maybe_fault("list_schemas")
        if fault is not None:
            return fault
        return Ok(DbPayload(payload={"schemas": ["public"]}, rows_count=1))

    async def list_tables(self, schema: str) -> Result[DbPayload, DatabaseFault]:
        fault = self._maybe_fault("list_tables")
        if fault is not None:
            return fault
        return Ok(DbPayload(payload={"tables": ["t"]}, rows_count=1))

    async def get_table_schema(self, schema: str, table: str) -> Result[DbPayload, DatabaseFault]:
        fault = self._maybe_fault("get_table_schema")
        if fault is not None:
            return fault
        return Ok(DbPayload(payload={"columns": ["id"]}, rows_count=1))

    async def select_rows(
        self,
        schema: str,
        table: str,
        columns: Sequence[str] | None,
        limit: int,
        offset: int,
    ) -> Result[DbPayload, DatabaseFault]:
        fault = self._maybe_fault("select_rows")
        if fault is not None:
            return fault
        return Ok(self.select_payload)

    async def execute_readonly(self, sql: str, max_rows: int) -> Result[DbPayload, DatabaseFault]:
        fault = self._maybe_fault("execute_readonly")
        if fault is not None:
            return fault
        return Ok(self.select_payload)

    async def execute_write(
        self, sql: str, target_table: str | None
    ) -> Result[DbPayload, DatabaseFault]:
        fault = self._maybe_fault("execute_write")
        if fault is not None:
            return fault
        return Ok(self.write_payload)

    async def explain(self, sql: str) -> Result[DbPayload, DatabaseFault]:
        fault = self._maybe_fault("explain")
        if fault is not None:
            return fault
        return Ok(DbPayload(payload={"plan": "Seq Scan"}, rows_count=None))

    async def database_stats(self) -> Result[DbPayload, DatabaseFault]:
        fault = self._maybe_fault("database_stats")
        if fault is not None:
            return fault
        return Ok(DbPayload(payload={"size": 1}, rows_count=None))


__all__ = ["FakeDatabaseGateway"]
