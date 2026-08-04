"""Pool factory unit tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from lime_ref_postgres_mcp.bootstrap.settings import Settings
from lime_ref_postgres_mcp.infrastructure.postgres.pool import create_pool


@pytest.mark.asyncio
async def test_create_pool_passes_settings(settings: Settings) -> None:
    fake = object()
    with patch(
        "lime_ref_postgres_mcp.infrastructure.postgres.pool.asyncpg.create_pool",
        new=AsyncMock(return_value=fake),
    ) as mocked:
        pool = await create_pool(settings)
        assert pool is fake
        kwargs = mocked.await_args.kwargs
        assert kwargs["dsn"] == settings.postgres_url
        assert kwargs["min_size"] == settings.pg_pool_min_size
        assert kwargs["max_size"] == settings.pg_pool_max_size
