"""DomainError hierarchy unit tests."""

from __future__ import annotations

import pytest

from lime_ref_postgres_mcp.domain.common.errors import (
    AgentNotAllowlisted,
    CapabilityDenied,
    DatabaseFault,
    DomainError,
    InvariantViolation,
    PassportInvalid,
    PassportMissing,
    PolicyStoreFault,
    SqlParseFault,
    StatementClassDenied,
    ToolInputInvalid,
)

_VARIANTS: list[type[DomainError]] = [
    InvariantViolation,
    AgentNotAllowlisted,
    CapabilityDenied,
    StatementClassDenied,
    ToolInputInvalid,
    PassportMissing,
    PassportInvalid,
    DatabaseFault,
    PolicyStoreFault,
    SqlParseFault,
]


def test_domain_error_str_and_fields() -> None:
    err = DomainError(
        invariant_id="test.code",
        message="failed",
        context={"agent_id": "a1"},
    )
    assert err.invariant_id == "test.code"
    assert err.message == "failed"
    assert err.context["agent_id"] == "a1"
    assert str(err) == "test.code: failed"


def test_invariant_violation_is_domain_error() -> None:
    err = InvariantViolation(
        invariant_id="domain.invariant_violation",
        message="broken",
        context={},
    )
    assert isinstance(err, DomainError)
    assert str(err) == "domain.invariant_violation: broken"


@pytest.mark.parametrize("cls", _VARIANTS, ids=[c.__name__ for c in _VARIANTS])
def test_err_variant_construction(cls: type[DomainError]) -> None:
    err = cls(
        invariant_id=f"test.{cls.__name__}",
        message="x",
        context={"k": 1},
    )
    assert isinstance(err, DomainError)
    assert isinstance(err, cls)
    assert err.context["k"] == 1


def test_err_agent_not_allowlisted() -> None:
    err = AgentNotAllowlisted(
        invariant_id="access.agent_not_allowlisted",
        message="nope",
        context={"agent_id": "x"},
    )
    assert isinstance(err, DomainError)


def test_err_capability_denied() -> None:
    err = CapabilityDenied(
        invariant_id="access.capability_denied",
        message="nope",
        context={},
    )
    assert isinstance(err, DomainError)


def test_err_statement_class_denied() -> None:
    err = StatementClassDenied(
        invariant_id="sql.statement_class_denied",
        message="nope",
        context={},
    )
    assert isinstance(err, DomainError)


def test_err_tool_input_invalid() -> None:
    err = ToolInputInvalid(
        invariant_id="tool.input_invalid",
        message="bad args",
        context={},
    )
    assert isinstance(err, DomainError)


def test_err_passport_missing() -> None:
    err = PassportMissing(invariant_id="auth.passport_missing", message="no bearer", context={})
    assert isinstance(err, DomainError)


def test_err_passport_invalid() -> None:
    err = PassportInvalid(invariant_id="auth.passport_invalid", message="bad jwt", context={})
    assert isinstance(err, DomainError)


def test_err_database_fault() -> None:
    err = DatabaseFault(invariant_id="db.fault", message="masked", context={})
    assert isinstance(err, DomainError)


def test_err_policy_store_fault() -> None:
    err = PolicyStoreFault(invariant_id="policy.store_fault", message="io", context={})
    assert isinstance(err, DomainError)


def test_err_sql_parse_fault() -> None:
    err = SqlParseFault(invariant_id="sql.parse_fault", message="parse", context={})
    assert isinstance(err, DomainError)


def test_domain_error_frozen() -> None:
    err = DomainError(invariant_id="a", message="b", context={})
    with pytest.raises(AttributeError):
        err.message = "mut"  # type: ignore[misc]
