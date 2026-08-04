"""Testcontainers fixtures for Postgres gateway integration tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import asyncpg
import pytest
from testcontainers.community.postgres import PostgresContainer

from lime_ref_postgres_mcp.bootstrap.settings import Settings
from lime_ref_postgres_mcp.infrastructure.postgres.asyncpg_database_gateway import (
    AsyncpgDatabaseGateway,
)


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("postgres:16-alpine") as postgres:
        url = postgres.get_connection_url()
        # testcontainers may return postgresql+psycopg2://
        yield url.replace("postgresql+psycopg2://", "postgresql://", 1)


@pytest.fixture
def integration_settings(postgres_url: str, full_env: dict[str, str]) -> Settings:
    env = dict(full_env)
    env["POSTGRES_URL"] = postgres_url
    env["PG_STATEMENT_TIMEOUT"] = "2s"
    env["PG_LOCK_TIMEOUT"] = "1s"
    env["PG_IDLE_IN_TRANSACTION_TIMEOUT"] = "5s"
    env["PG_MAX_RESULT_BYTES"] = "1048576"
    return Settings.from_env(env)


@pytest.fixture
async def database(
    postgres_url: str, integration_settings: Settings
) -> AsyncIterator[AsyncpgDatabaseGateway]:
    pool = await asyncpg.create_pool(postgres_url, min_size=1, max_size=2)
    gw = AsyncpgDatabaseGateway(
        pool,
        statement_timeout=integration_settings.pg_statement_timeout,
        lock_timeout=integration_settings.pg_lock_timeout,
        idle_in_transaction_timeout=integration_settings.pg_idle_in_transaction_timeout,
        max_result_bytes=integration_settings.pg_max_result_bytes,
    )
    try:
        yield gw
    finally:
        await pool.close()
