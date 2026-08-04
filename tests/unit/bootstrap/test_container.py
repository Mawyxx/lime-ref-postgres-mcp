"""Composition root unit tests."""

from __future__ import annotations

import pytest

from lime_ref_postgres_mcp.application.services.invoke_agent_tool import InvokeAgentToolService
from lime_ref_postgres_mcp.bootstrap.container import (
    Runtime,
    build_runtime,
    build_scaffold_runtime,
    create_database,
    create_passport_verifier,
    create_policy_store,
)
from lime_ref_postgres_mcp.bootstrap.scaffold import (
    ScaffoldRejectVerifier,
    ScaffoldUnavailableDatabase,
    ScaffoldUnavailablePolicyStore,
)
from lime_ref_postgres_mcp.bootstrap.settings import Settings
from lime_ref_postgres_mcp.infrastructure.clock.system_clock import SystemClock
from lime_ref_postgres_mcp.infrastructure.clock.uuid_id_generator import Uuid4IdGenerator
from lime_ref_postgres_mcp.infrastructure.events.in_process_event_bus import InProcessEventBus
from lime_ref_postgres_mcp.infrastructure.identity.lime_passport_verifier import (
    LimePassportVerifier,
)
from lime_ref_postgres_mcp.infrastructure.policy.json_agent_policy_store import (
    JsonAgentPolicyStore,
)
from lime_ref_postgres_mcp.infrastructure.postgres.asyncpg_database_gateway import (
    AsyncpgDatabaseGateway,
)
from lime_ref_postgres_mcp.infrastructure.sql.pglast_sql_analyzer import PglastSqlAnalyzer


def test_build_runtime_with_settings(settings: Settings) -> None:
    runtime = build_runtime(
        settings,
        verifier=ScaffoldRejectVerifier(),
        policy_store=ScaffoldUnavailablePolicyStore(),
        database=ScaffoldUnavailableDatabase(),
    )
    assert isinstance(runtime, Runtime)
    assert runtime.settings is settings
    assert isinstance(runtime.clock, SystemClock)
    assert isinstance(runtime.ids, Uuid4IdGenerator)
    assert isinstance(runtime.sql_analyzer, PglastSqlAnalyzer)
    assert isinstance(runtime.event_bus, InProcessEventBus)
    assert isinstance(runtime.invoke_agent_tool, InvokeAgentToolService)
    event_id = runtime.ids.new_event_id()
    request_id = runtime.ids.new_request_id()
    assert event_id
    assert request_id
    assert event_id != request_id
    assert runtime.clock.now_utc().tzinfo is not None


def test_build_runtime_loads_env(
    monkeypatch: pytest.MonkeyPatch,
    full_env: dict[str, str],
) -> None:
    for key, value in full_env.items():
        monkeypatch.setenv(key, value)
    runtime = build_runtime(
        verifier=ScaffoldRejectVerifier(),
        policy_store=ScaffoldUnavailablePolicyStore(),
        database=ScaffoldUnavailableDatabase(),
    )
    assert runtime.settings.lime_expected_domain == "example.com"


def test_create_factories_share_clock(settings: Settings) -> None:
    clock = SystemClock()
    verifier = create_passport_verifier(settings)
    store = create_policy_store(settings, clock)
    assert isinstance(verifier, LimePassportVerifier)
    assert isinstance(store, JsonAgentPolicyStore)
    runtime = build_runtime(
        settings,
        verifier=verifier,
        policy_store=store,
        database=ScaffoldUnavailableDatabase(),
        clock=clock,
    )
    assert runtime.clock is clock
    assert runtime.verifier is verifier
    assert runtime.policy_store is store
    verifier.close()


def test_create_database_and_scaffold_runtime(settings: Settings) -> None:
    db = create_database(settings)
    assert isinstance(db, AsyncpgDatabaseGateway)
    assert db._pool is None
    runtime = build_scaffold_runtime(settings)
    assert isinstance(runtime.database, AsyncpgDatabaseGateway)
    assert runtime.database._pool is None  # type: ignore[attr-defined]
    # ConsoleSink subscribed on InProcessEventBus when enabled
    bus = runtime.event_bus
    assert isinstance(bus, InProcessEventBus)
    assert len(bus._handlers) == 1  # type: ignore[attr-defined]


def test_scaffold_skips_console_when_disabled(settings: Settings) -> None:
    from dataclasses import replace

    disabled = replace(settings, enable_console_event_sink=False)
    runtime = build_scaffold_runtime(disabled)
    bus = runtime.event_bus
    assert isinstance(bus, InProcessEventBus)
    assert bus._handlers == []  # type: ignore[attr-defined]
