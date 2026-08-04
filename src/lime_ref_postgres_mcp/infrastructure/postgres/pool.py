"""asyncpg pool factory from Settings (composition / gateway lazy open)."""

from __future__ import annotations

import asyncpg

from lime_ref_postgres_mcp.bootstrap.settings import Settings


async def create_pool(settings: Settings) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn=settings.postgres_url,
        min_size=settings.pg_pool_min_size,
        max_size=settings.pg_pool_max_size,
    )


__all__ = ["create_pool"]
