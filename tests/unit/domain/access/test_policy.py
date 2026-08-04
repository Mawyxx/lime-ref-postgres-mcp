"""PolicyDocument / AgentPolicy unit tests."""

from __future__ import annotations

import pytest

from lime_ref_postgres_mcp.domain.access.authorized_agent import AuthorizedAgent
from lime_ref_postgres_mcp.domain.access.capability import ToolCapability
from lime_ref_postgres_mcp.domain.access.policy import DEFAULT_PERMISSIONS, PolicyDocument
from lime_ref_postgres_mcp.domain.agent.agent_id import AgentId
from lime_ref_postgres_mcp.domain.common.errors import AgentNotAllowlisted, InvariantViolation
from lime_ref_postgres_mcp.domain.common.result import Err, unwrap, unwrap_err


def _aid(raw: str = "agent_abc123") -> AgentId:
    return unwrap(AgentId.parse(raw))


def test_pol1_unknown_agent_not_allowlisted() -> None:
    doc = unwrap(
        PolicyDocument.from_mapping(
            {"max_rows": 10, "agents": {"agent_abc123": {"permissions": ["READ_DATA"]}}}
        )
    )
    result = doc.resolve(_aid("missing"))
    assert isinstance(result, Err)
    err = unwrap_err(result)
    assert isinstance(err, AgentNotAllowlisted)
    assert err.invariant_id == "access.agent_not_allowlisted"


def test_pol2_missing_permissions_defaults() -> None:
    doc = unwrap(PolicyDocument.from_mapping({"max_rows": 50, "agents": {"agent_x": {}}}))
    policy = unwrap(doc.resolve(_aid("agent_x")))
    assert policy.permissions == DEFAULT_PERMISSIONS
    assert policy.has(ToolCapability.READ_SCHEMA)
    assert policy.has(ToolCapability.READ_DATA)


def test_pol3_empty_permissions_has_false() -> None:
    doc = unwrap(
        PolicyDocument.from_mapping({"max_rows": 10, "agents": {"agent_x": {"permissions": []}}})
    )
    policy = unwrap(doc.resolve(_aid("agent_x")))
    assert policy.permissions == frozenset()
    assert not policy.has(ToolCapability.READ_DATA)
    assert not policy.has_all({ToolCapability.READ_SCHEMA})


def test_pol4_clamp_limit() -> None:
    doc = unwrap(PolicyDocument.from_mapping({"max_rows": 100, "agents": {}}))
    assert doc.clamp_limit(500) == 100
    assert doc.clamp_limit(10) == 10
    assert doc.clamp_limit(None) == 100
    assert doc.clamp_limit(0) == 100


def test_pol5_max_rows_invalid() -> None:
    result = PolicyDocument.from_mapping({"max_rows": 0, "agents": {}})
    assert isinstance(result, Err)
    assert unwrap_err(result).invariant_id == "policy.max_rows_invalid"


def test_from_mapping_unknown_capability() -> None:
    result = PolicyDocument.from_mapping(
        {"max_rows": 10, "agents": {"a1": {"permissions": ["NOPE"]}}}
    )
    assert isinstance(result, Err)
    assert unwrap_err(result).invariant_id == "policy.capability_unknown"


def test_from_mapping_bool_max_rows_rejected() -> None:
    result = PolicyDocument.from_mapping({"max_rows": True, "agents": {}})
    assert isinstance(result, Err)


def test_from_mapping_agents_not_mapping() -> None:
    result = PolicyDocument.from_mapping({"max_rows": 10, "agents": []})
    assert isinstance(result, Err)
    assert unwrap_err(result).invariant_id == "policy.agents_invalid"


def test_from_mapping_permissions_not_list() -> None:
    result = PolicyDocument.from_mapping(
        {"max_rows": 10, "agents": {"a1": {"permissions": "READ_DATA"}}}
    )
    assert isinstance(result, Err)
    assert unwrap_err(result).invariant_id == "policy.permissions_invalid"


def test_from_mapping_capability_not_string() -> None:
    result = PolicyDocument.from_mapping({"max_rows": 10, "agents": {"a1": {"permissions": [1]}}})
    assert isinstance(result, Err)
    assert unwrap_err(result).invariant_id == "policy.capability_invalid"


def test_from_mapping_agent_entry_invalid() -> None:
    result = PolicyDocument.from_mapping({"max_rows": 10, "agents": {"a1": "x"}})
    assert isinstance(result, Err)
    assert unwrap_err(result).invariant_id == "policy.agent_entry_invalid"


def test_from_mapping_root_not_mapping() -> None:
    result = PolicyDocument.from_mapping([])  # type: ignore[arg-type]
    assert isinstance(result, Err)
    assert isinstance(unwrap_err(result), InvariantViolation)


def test_from_mapping_empty_agent_id() -> None:
    result = PolicyDocument.from_mapping({"max_rows": 10, "agents": {"  ": {}}})
    assert isinstance(result, Err)


def test_authorized_agent_from_policy() -> None:
    doc = unwrap(
        PolicyDocument.from_mapping(
            {
                "max_rows": 10,
                "agents": {"agent_x": {"permissions": ["READ_SCHEMA", "READ_DATA"]}},
            }
        )
    )
    policy = unwrap(doc.resolve(_aid("agent_x")))
    auth = AuthorizedAgent.from_policy(policy, domain="lime.pics")
    assert auth.agent_id.value == "agent_x"
    assert auth.domain == "lime.pics"
    assert ToolCapability.READ_DATA in auth.permissions


def test_policy_frozen() -> None:
    doc = unwrap(PolicyDocument.from_mapping({"max_rows": 10, "agents": {}}))
    with pytest.raises(AttributeError):
        doc.max_rows = 99  # type: ignore[misc]
