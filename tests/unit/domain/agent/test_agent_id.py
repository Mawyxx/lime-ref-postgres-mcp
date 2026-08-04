"""AgentId unit tests."""

from __future__ import annotations

import pytest

from lime_ref_postgres_mcp.domain.agent.agent_id import AgentId
from lime_ref_postgres_mcp.domain.common.errors import InvariantViolation
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, unwrap, unwrap_err


def test_parse_strips_and_accepts() -> None:
    result = AgentId.parse("  agent_abc  ")
    assert isinstance(result, Ok)
    agent = unwrap(result)
    assert agent.value == "agent_abc"
    assert str(agent) == "agent_abc"


def test_parse_empty_rejected() -> None:
    result = AgentId.parse("   ")
    assert isinstance(result, Err)
    err = unwrap_err(result)
    assert isinstance(err, InvariantViolation)
    assert err.invariant_id == "agent.id_empty"


def test_parse_non_string_rejected() -> None:
    result = AgentId.parse(123)
    assert isinstance(result, Err)
    assert unwrap_err(result).invariant_id == "agent.id_invalid"


def test_frozen_agent_id() -> None:
    agent = unwrap(AgentId.parse("a1"))
    with pytest.raises(AttributeError):
        agent.value = "mutated"  # type: ignore[misc]
