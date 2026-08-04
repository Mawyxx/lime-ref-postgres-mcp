"""Shared fixtures for lime_ref_postgres_mcp tests."""

from __future__ import annotations

import pytest

from lime_ref_postgres_mcp.bootstrap.settings import Settings


@pytest.fixture
def full_env() -> dict[str, str]:
    return {
        "LIME_EXPECTED_DOMAIN": "example.com",
        "LIME_JWKS_URL": "https://lime.pics/.well-known/jwks.json",
        "POSTGRES_URL": "postgresql://user:pass@localhost:5432/db",
        "AGENTS_POLICY_PATH": "./config/agents.example.json",
        "POLICY_RELOAD_TTL_SECONDS": "60",
        "PG_STATEMENT_TIMEOUT": "5s",
        "PG_LOCK_TIMEOUT": "2s",
        "PG_IDLE_IN_TRANSACTION_TIMEOUT": "10s",
        "PG_MAX_RESULT_BYTES": "1048576",
        "PG_POOL_MIN_SIZE": "1",
        "PG_POOL_MAX_SIZE": "4",
        "ENABLE_CONSOLE_EVENT_SINK": "1",
    }


@pytest.fixture
def settings(full_env: dict[str, str]) -> Settings:
    return Settings.from_env(full_env)
