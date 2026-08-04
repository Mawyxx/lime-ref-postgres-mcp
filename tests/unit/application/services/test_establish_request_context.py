"""EstablishRequestContext unit tests."""

from __future__ import annotations

import pytest
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.identity import FakePassportVerifier
from tests.fakes.policy import FakePolicyStore
from tests.fakes.sequence_ids import SequenceIds

from lime_ref_postgres_mcp.application.commands.invoke_agent_tool import InvokeAgentToolCommand
from lime_ref_postgres_mcp.application.services.establish_request_context import (
    EstablishRequestContextService,
)
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName
from lime_ref_postgres_mcp.domain.common.errors import (
    AgentNotAllowlisted,
    PassportInvalid,
    PassportMissing,
    PolicyStoreFault,
)
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, unwrap


@pytest.fixture
def establish() -> EstablishRequestContextService:
    return EstablishRequestContextService(
        verifier=FakePassportVerifier(),
        policy_store=FakePolicyStore(),
        clock=FixedClock(),
        ids=SequenceIds(),
    )


@pytest.mark.asyncio
async def test_missing_bearer(establish: EstablishRequestContextService) -> None:
    result = await establish.execute(
        InvokeAgentToolCommand(bearer_token=None, tool=ToolName.LIST_SCHEMAS, args={})
    )
    assert isinstance(result, Err)
    assert isinstance(result.error, PassportMissing)


@pytest.mark.asyncio
async def test_blank_bearer_never_calls_verifier() -> None:
    verifier = FakePassportVerifier()
    svc = EstablishRequestContextService(
        verifier=verifier,
        policy_store=FakePolicyStore(),
        clock=FixedClock(),
        ids=SequenceIds(),
    )
    result = await svc.execute(
        InvokeAgentToolCommand(bearer_token="   ", tool=ToolName.LIST_SCHEMAS, args={})
    )
    assert isinstance(result, Err)
    assert verifier.calls == []


@pytest.mark.asyncio
async def test_bad_jwt() -> None:
    svc = EstablishRequestContextService(
        verifier=FakePassportVerifier(),
        policy_store=FakePolicyStore(),
        clock=FixedClock(),
        ids=SequenceIds(),
    )
    result = await svc.execute(
        InvokeAgentToolCommand(bearer_token="bad", tool=ToolName.LIST_SCHEMAS, args={})
    )
    assert isinstance(result, Err)
    assert isinstance(result.error, PassportInvalid)


@pytest.mark.asyncio
async def test_not_allowlisted(establish: EstablishRequestContextService) -> None:
    from lime_ref_postgres_mcp.application.ports.identity import PassportClaims
    from lime_ref_postgres_mcp.domain.agent.agent_id import AgentId

    verifier = FakePassportVerifier()
    verifier.register(
        "tok",
        PassportClaims(agent_id=unwrap(AgentId.parse("unknown_agent")), domain="example.com"),
    )
    svc = EstablishRequestContextService(
        verifier=verifier,
        policy_store=FakePolicyStore(),
        clock=FixedClock(),
        ids=SequenceIds(),
    )
    result = await svc.execute(
        InvokeAgentToolCommand(bearer_token="tok", tool=ToolName.LIST_SCHEMAS, args={})
    )
    assert isinstance(result, Err)
    assert isinstance(result.error, AgentNotAllowlisted)


@pytest.mark.asyncio
async def test_policy_store_fault() -> None:
    store = FakePolicyStore()
    store.fault = PolicyStoreFault(
        invariant_id="policy.store_fault", message="cannot load", context={}
    )
    svc = EstablishRequestContextService(
        verifier=FakePassportVerifier(),
        policy_store=store,
        clock=FixedClock(),
        ids=SequenceIds(),
    )
    result = await svc.execute(
        InvokeAgentToolCommand(bearer_token="tok", tool=ToolName.LIST_SCHEMAS, args={})
    )
    assert isinstance(result, Err)
    assert isinstance(result.error, PolicyStoreFault)


@pytest.mark.asyncio
async def test_ok_builds_context(establish: EstablishRequestContextService) -> None:
    result = await establish.execute(
        InvokeAgentToolCommand(
            bearer_token="good",
            tool=ToolName.SELECT_ROWS,
            args={"schema": "public", "table": "t"},
            request_id="req-fixed",
        )
    )
    assert isinstance(result, Ok)
    ctx = unwrap(result)
    assert ctx.request_id == "req-fixed"
    assert ctx.tool is ToolName.SELECT_ROWS
    assert "bearer" not in ctx.args
    assert ctx.agent.agent_id.value == "agent_ok"
