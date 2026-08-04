"""Map asyncpg/OS exceptions to masked DatabaseFault."""

from __future__ import annotations

import asyncio

import asyncpg

from lime_ref_postgres_mcp.domain.common.errors import DatabaseFault


def map_asyncpg_fault(exc: BaseException) -> DatabaseFault:
    if isinstance(exc, asyncpg.exceptions.LockNotAvailableError):
        return DatabaseFault(
            invariant_id="database.lock_timeout",
            message="Database operation could not acquire a lock",
            context={},
        )
    if isinstance(exc, (asyncpg.exceptions.QueryCanceledError, TimeoutError, asyncio.TimeoutError)):
        return DatabaseFault(
            invariant_id="database.timeout",
            message="Database operation timed out",
            context={},
        )
    if isinstance(exc, (OSError, asyncpg.exceptions.PostgresConnectionError, ConnectionError)):
        return DatabaseFault(
            invariant_id="database.unavailable",
            message="Database is temporarily unavailable",
            context={},
        )
    return DatabaseFault(
        invariant_id="database.execution_failed",
        message="Database operation failed",
        context={},
    )


__all__ = ["map_asyncpg_fault"]
