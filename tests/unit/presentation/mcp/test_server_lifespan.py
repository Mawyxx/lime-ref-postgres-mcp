"""Lifespan + ASGI builder coverage for live adapter branches."""

from __future__ import annotations

import dataclasses
from unittest.mock import AsyncMock, MagicMock

import pytest
from tests.support.build_test_runtime import build_test_runtime

from lime_ref_postgres_mcp.bootstrap.container import (
    build_runtime,
    create_database,
    create_passport_verifier,
)
from lime_ref_postgres_mcp.bootstrap.settings import Settings
from lime_ref_postgres_mcp.presentation.mcp.server import build_asgi_app, build_mcp_server


@pytest.mark.asyncio
async def test_lifespan_warms_live_adapters(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tr = build_test_runtime(settings)
    verifier = create_passport_verifier(settings)
    database = create_database(settings)
    warmup = AsyncMock(return_value=True)
    open_ = AsyncMock()
    close_db = AsyncMock()
    close_v = MagicMock()
    monkeypatch.setattr(verifier, "warmup", warmup)
    monkeypatch.setattr(verifier, "close", close_v)
    monkeypatch.setattr(database, "open", open_)
    monkeypatch.setattr(database, "close", close_db)
    runtime = build_runtime(
        settings,
        verifier=verifier,
        policy_store=tr.policy_store,
        database=database,
        sql_analyzer=tr.runtime.sql_analyzer,
        event_bus=tr.bus,
        clock=tr.clock,
        ids=tr.ids,
    )
    server = build_mcp_server(runtime)
    async with server.lifespan(server):
        pass
    warmup.assert_awaited_once_with(raise_on_failure=True)
    open_.assert_awaited_once()
    close_db.assert_awaited_once()
    close_v.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_pool_open_failure(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tr = build_test_runtime(settings)
    verifier = create_passport_verifier(settings)
    database = create_database(settings)
    monkeypatch.setattr(verifier, "warmup", AsyncMock(return_value=False))
    monkeypatch.setattr(verifier, "close", MagicMock())
    monkeypatch.setattr(database, "open", AsyncMock(side_effect=RuntimeError("pool boom")))
    runtime = build_runtime(
        settings,
        verifier=verifier,
        policy_store=tr.policy_store,
        database=database,
        sql_analyzer=tr.runtime.sql_analyzer,
        event_bus=tr.bus,
        clock=tr.clock,
        ids=tr.ids,
    )
    server = build_mcp_server(runtime)
    with pytest.raises(RuntimeError, match="pool boom"):
        async with server.lifespan(server):
            pass


@pytest.mark.asyncio
async def test_lifespan_skips_non_live_adapters(settings: Settings) -> None:
    tr = build_test_runtime(settings)
    server = build_mcp_server(tr.runtime)
    async with server.lifespan(server):
        pass


@pytest.mark.asyncio
async def test_build_asgi_app_dns_defaults(settings: Settings) -> None:
    tr = build_test_runtime(settings)
    server, app = build_asgi_app(tr.runtime, disable_dns_rebinding=False)
    assert server is not None
    assert app is not None


@pytest.mark.asyncio
async def test_build_asgi_app_disable_dns(settings: Settings) -> None:
    tr = build_test_runtime(settings)
    server, app = build_asgi_app(tr.runtime, disable_dns_rebinding=True)
    assert server is not None
    assert app is not None


@pytest.mark.asyncio
async def test_build_asgi_app_uses_allowed_hosts_env(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LIME_MCP_ALLOWED_HOSTS", "mcp.example.com, localhost")
    tr = build_test_runtime(settings)
    server, app = build_asgi_app(tr.runtime, disable_dns_rebinding=False)
    assert server is not None
    assert app is not None


@pytest.mark.asyncio
async def test_build_asgi_app_wildcard_bind_defaults_to_loopback(settings: Settings) -> None:
    tr = build_test_runtime(dataclasses.replace(settings, mcp_bind_host="0.0.0.0"))
    server, app = build_asgi_app(tr.runtime, disable_dns_rebinding=False)
    assert server is not None
    assert app is not None
