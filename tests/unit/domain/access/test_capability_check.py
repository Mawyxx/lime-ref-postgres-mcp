"""capability_check unit tests."""

from __future__ import annotations

import pytest

from lime_ref_postgres_mcp.domain.access.capability import ToolCapability
from lime_ref_postgres_mcp.domain.access.capability_check import (
    CapabilityDecision,
    capability_check,
)
from lime_ref_postgres_mcp.domain.access.policy import REASON_CAPABILITY_DENIED
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import REQUIRED_CAPABILITY, ToolName
from lime_ref_postgres_mcp.domain.common.errors import CapabilityDenied


@pytest.mark.parametrize("tool", list(ToolName), ids=[t.value for t in ToolName])
def test_cap1_allowed_when_required_present(tool: ToolName) -> None:
    required = REQUIRED_CAPABILITY[tool]
    decision = capability_check(tool, frozenset({required}))
    assert decision.allowed is True
    assert decision.required == required
    assert decision.missing == frozenset()
    assert decision.reason_code is None
    assert decision.to_denied_error() is None


def test_cap2_write_without_write_data() -> None:
    decision = capability_check(
        ToolName.EXECUTE_WRITE_QUERY,
        frozenset({ToolCapability.READ_DATA, ToolCapability.READ_SCHEMA}),
    )
    assert decision.allowed is False
    assert decision.reason_code == REASON_CAPABILITY_DENIED
    assert decision.missing == frozenset({ToolCapability.WRITE_DATA})
    err = decision.to_denied_error()
    assert isinstance(err, CapabilityDenied)
    assert err.invariant_id == "access.capability_denied"


def test_cap3_admin_without_admin() -> None:
    decision = capability_check(ToolName.GET_DATABASE_STATS, frozenset({ToolCapability.READ_DATA}))
    assert decision.allowed is False
    assert decision.required == ToolCapability.ADMIN
    assert isinstance(decision.to_denied_error(), CapabilityDenied)


def test_capability_decision_frozen() -> None:
    d = CapabilityDecision(
        allowed=True,
        required=ToolCapability.READ_DATA,
        missing=frozenset(),
    )
    with pytest.raises(AttributeError):
        d.allowed = False  # type: ignore[misc]
