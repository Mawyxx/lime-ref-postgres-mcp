"""Composition root — wire P2/P3 runtime (Prime A06)."""

from __future__ import annotations

from dataclasses import dataclass

from lime_ref_postgres_mcp.application.ports.clock import Clock, IdGenerator
from lime_ref_postgres_mcp.application.ports.database import DatabaseGateway
from lime_ref_postgres_mcp.application.ports.events import EventBus
from lime_ref_postgres_mcp.application.ports.identity import PassportVerifier
from lime_ref_postgres_mcp.application.ports.policy import AgentPolicyStore
from lime_ref_postgres_mcp.application.ports.sql_analyzer import SqlAnalyzer
from lime_ref_postgres_mcp.application.services.authorize_tool import AuthorizeToolService
from lime_ref_postgres_mcp.application.services.emit_agent_action import EmitAgentActionService
from lime_ref_postgres_mcp.application.services.establish_request_context import (
    EstablishRequestContextService,
)
from lime_ref_postgres_mcp.application.services.invoke_agent_tool import InvokeAgentToolService
from lime_ref_postgres_mcp.bootstrap.observability import configure_observability
from lime_ref_postgres_mcp.bootstrap.settings import Settings
from lime_ref_postgres_mcp.infrastructure.clock.system_clock import SystemClock
from lime_ref_postgres_mcp.infrastructure.clock.uuid_id_generator import Uuid4IdGenerator
from lime_ref_postgres_mcp.infrastructure.events.in_process_event_bus import InProcessEventBus
from lime_ref_postgres_mcp.infrastructure.identity.lime_base_url import base_url_from_jwks_url
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
from lime_ref_postgres_mcp.subscribers.console_sink import ConsoleSink


@dataclass(frozen=True, slots=True)
class Runtime:
    """Process graph: settings + ports + invoke facade."""

    settings: Settings
    clock: Clock
    ids: IdGenerator
    sql_analyzer: SqlAnalyzer
    event_bus: EventBus
    verifier: PassportVerifier
    policy_store: AgentPolicyStore
    database: DatabaseGateway
    invoke_agent_tool: InvokeAgentToolService


def create_passport_verifier(settings: Settings) -> LimePassportVerifier:
    try:
        base_url = base_url_from_jwks_url(settings.lime_jwks_url)
    except ValueError as exc:
        from lime_ref_postgres_mcp.bootstrap.settings import ConfigurationError

        raise ConfigurationError(str(exc)) from exc
    return LimePassportVerifier(
        expected_domain=settings.lime_expected_domain,
        base_url=base_url,
        audience=settings.lime_expected_aud,
        cache_ttl=settings.lime_jwks_cache_ttl_seconds,
        leeway_seconds=settings.lime_jwt_leeway_seconds,
    )


def create_policy_store(settings: Settings, clock: Clock) -> JsonAgentPolicyStore:
    return JsonAgentPolicyStore(
        settings.agents_policy_path,
        clock=clock,
        reload_ttl_seconds=settings.policy_reload_ttl_seconds,
    )


def create_database(settings: Settings) -> AsyncpgDatabaseGateway:
    return AsyncpgDatabaseGateway.from_settings(settings)


def _configure_from_settings(settings: Settings) -> None:
    configure_observability(
        level=settings.log_level,
        format=settings.log_format,
        stream_name=settings.log_stream,
        metrics_enabled=settings.metrics_enabled,
    )


def subscribe_console_sink(runtime: Runtime) -> None:
    """Wire ConsoleSink when enabled (composition edge only)."""
    if runtime.settings.enable_console_event_sink:
        runtime.event_bus.subscribe(ConsoleSink())


def build_scaffold_runtime(settings: Settings | None = None) -> Runtime:
    """Compose Lime identity + JSON policy + asyncpg DB (lazy pool)."""
    resolved = Settings.from_env() if settings is None else settings
    _configure_from_settings(resolved)
    clock = SystemClock()
    runtime = build_runtime(
        resolved,
        verifier=create_passport_verifier(resolved),
        policy_store=create_policy_store(resolved, clock),
        database=create_database(resolved),
        clock=clock,
    )
    subscribe_console_sink(runtime)
    return runtime


def build_runtime(
    settings: Settings | None = None,
    *,
    verifier: PassportVerifier,
    policy_store: AgentPolicyStore,
    database: DatabaseGateway,
    sql_analyzer: SqlAnalyzer | None = None,
    event_bus: EventBus | None = None,
    clock: Clock | None = None,
    ids: IdGenerator | None = None,
) -> Runtime:
    resolved = Settings.from_env() if settings is None else settings
    _configure_from_settings(resolved)
    clock_impl: Clock = SystemClock() if clock is None else clock
    ids_impl: IdGenerator = Uuid4IdGenerator() if ids is None else ids
    analyzer: SqlAnalyzer = PglastSqlAnalyzer() if sql_analyzer is None else sql_analyzer
    bus: EventBus = InProcessEventBus() if event_bus is None else event_bus
    establish = EstablishRequestContextService(
        verifier=verifier,
        policy_store=policy_store,
        clock=clock_impl,
        ids=ids_impl,
    )
    authorize = AuthorizeToolService(analyzer=analyzer)
    emit = EmitAgentActionService(event_bus=bus, clock=clock_impl, ids=ids_impl)
    invoke = InvokeAgentToolService(
        establish=establish,
        authorize=authorize,
        emit=emit,
        database=database,
    )
    return Runtime(
        settings=resolved,
        clock=clock_impl,
        ids=ids_impl,
        sql_analyzer=analyzer,
        event_bus=bus,
        verifier=verifier,
        policy_store=policy_store,
        database=database,
        invoke_agent_tool=invoke,
    )


__all__ = [
    "Runtime",
    "build_runtime",
    "build_scaffold_runtime",
    "create_database",
    "create_passport_verifier",
    "create_policy_store",
    "subscribe_console_sink",
]
