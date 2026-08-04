"""Wire InvokeAgentToolService with test doubles."""

from __future__ import annotations

from dataclasses import dataclass

from tests.fakes.database import FakeDatabaseGateway
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.identity import FakePassportVerifier
from tests.fakes.policy import FakePolicyStore
from tests.fakes.recording_event_bus import RecordingEventBus
from tests.fakes.sequence_ids import SequenceIds
from tests.fakes.sql_analyzer import FakeSqlAnalyzer

from lime_ref_postgres_mcp.application.ports.sql_analyzer import SqlAnalyzer
from lime_ref_postgres_mcp.application.services.authorize_tool import AuthorizeToolService
from lime_ref_postgres_mcp.application.services.emit_agent_action import EmitAgentActionService
from lime_ref_postgres_mcp.application.services.establish_request_context import (
    EstablishRequestContextService,
)
from lime_ref_postgres_mcp.application.services.invoke_agent_tool import InvokeAgentToolService
from lime_ref_postgres_mcp.bootstrap.container import Runtime, build_runtime
from lime_ref_postgres_mcp.bootstrap.settings import Settings
from lime_ref_postgres_mcp.domain.access.policy import PolicyDocument
from lime_ref_postgres_mcp.infrastructure.sql.pglast_sql_analyzer import PglastSqlAnalyzer


@dataclass(frozen=True, slots=True)
class TestRuntime:
    runtime: Runtime
    bus: RecordingEventBus
    verifier: FakePassportVerifier
    policy_store: FakePolicyStore
    database: FakeDatabaseGateway
    clock: FixedClock
    ids: SequenceIds


def build_test_runtime(
    settings: Settings,
    *,
    policy: PolicyDocument | None = None,
    analyzer: SqlAnalyzer | None = None,
    use_pglast: bool = False,
) -> TestRuntime:
    clock = FixedClock()
    ids = SequenceIds()
    bus = RecordingEventBus()
    verifier = FakePassportVerifier()
    policy_store = FakePolicyStore(policy)
    database = FakeDatabaseGateway()
    sql_analyzer: SqlAnalyzer
    if analyzer is not None:
        sql_analyzer = analyzer
    elif use_pglast:
        sql_analyzer = PglastSqlAnalyzer()
    else:
        sql_analyzer = FakeSqlAnalyzer()
    runtime = build_runtime(
        settings,
        verifier=verifier,
        policy_store=policy_store,
        database=database,
        sql_analyzer=sql_analyzer,
        event_bus=bus,
        clock=clock,
        ids=ids,
    )
    return TestRuntime(
        runtime=runtime,
        bus=bus,
        verifier=verifier,
        policy_store=policy_store,
        database=database,
        clock=clock,
        ids=ids,
    )


def wire_invoke(
    *,
    verifier: FakePassportVerifier | None = None,
    policy_store: FakePolicyStore | None = None,
    database: FakeDatabaseGateway | None = None,
    analyzer: SqlAnalyzer | None = None,
    bus: RecordingEventBus | None = None,
    clock: FixedClock | None = None,
    ids: SequenceIds | None = None,
) -> tuple[InvokeAgentToolService, RecordingEventBus]:
    clock = clock or FixedClock()
    ids = ids or SequenceIds()
    bus = bus or RecordingEventBus()
    verifier = verifier or FakePassportVerifier()
    policy_store = policy_store or FakePolicyStore()
    database = database or FakeDatabaseGateway()
    analyzer = analyzer or FakeSqlAnalyzer()
    establish = EstablishRequestContextService(
        verifier=verifier, policy_store=policy_store, clock=clock, ids=ids
    )
    authorize = AuthorizeToolService(analyzer=analyzer)
    emit = EmitAgentActionService(event_bus=bus, clock=clock, ids=ids)
    invoke = InvokeAgentToolService(
        establish=establish, authorize=authorize, emit=emit, database=database
    )
    return invoke, bus


__all__ = ["TestRuntime", "build_test_runtime", "wire_invoke"]
