"""Fail-closed scaffold adapters for composition smoke (__main__) — not a DEBUG bypass."""

from __future__ import annotations

from collections.abc import Sequence

from lime_ref_postgres_mcp.application.context.db_payload import DbPayload
from lime_ref_postgres_mcp.application.ports.identity import PassportClaims
from lime_ref_postgres_mcp.domain.access.policy import PolicyDocument
from lime_ref_postgres_mcp.domain.common.errors import (
    DatabaseFault,
    PassportInvalid,
    PolicyStoreFault,
)
from lime_ref_postgres_mcp.domain.common.result import Err, Result


class ScaffoldRejectVerifier:
    """Always rejects — scaffold has no JWKS (P3)."""

    async def verify(self, bearer_token: str) -> Result[PassportClaims, PassportInvalid]:
        return Err(
            PassportInvalid(
                invariant_id="identity.passport_invalid",
                message="scaffold verifier rejects all tokens (no JWKS wired)",
                context={},
            )
        )


class ScaffoldUnavailablePolicyStore:
    """Always faults — scaffold has no JsonPolicyStore (P3)."""

    async def current(self) -> Result[PolicyDocument, PolicyStoreFault]:
        return Err(
            PolicyStoreFault(
                invariant_id="policy.store_unavailable",
                message="scaffold policy store unavailable (no JsonPolicy wired)",
                context={},
            )
        )


class ScaffoldUnavailableDatabase:
    """Always faults — scaffold has no asyncpg (P4)."""

    async def list_schemas(self) -> Result[DbPayload, DatabaseFault]:
        return self._fault()

    async def list_tables(self, schema: str) -> Result[DbPayload, DatabaseFault]:
        return self._fault()

    async def get_table_schema(self, schema: str, table: str) -> Result[DbPayload, DatabaseFault]:
        return self._fault()

    async def select_rows(
        self,
        schema: str,
        table: str,
        columns: Sequence[str] | None,
        limit: int,
        offset: int,
    ) -> Result[DbPayload, DatabaseFault]:
        return self._fault()

    async def execute_readonly(self, sql: str, max_rows: int) -> Result[DbPayload, DatabaseFault]:
        return self._fault()

    async def execute_write(
        self, sql: str, target_table: str | None
    ) -> Result[DbPayload, DatabaseFault]:
        return self._fault()

    async def explain(self, sql: str) -> Result[DbPayload, DatabaseFault]:
        return self._fault()

    async def database_stats(self) -> Result[DbPayload, DatabaseFault]:
        return self._fault()

    def _fault(self) -> Result[DbPayload, DatabaseFault]:
        return Err(
            DatabaseFault(
                invariant_id="database.unavailable",
                message="scaffold database unavailable (no asyncpg wired)",
                context={},
            )
        )


__all__ = [
    "ScaffoldRejectVerifier",
    "ScaffoldUnavailableDatabase",
    "ScaffoldUnavailablePolicyStore",
]
