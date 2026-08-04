"""Shared domain primitives: Result and errors."""

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
from lime_ref_postgres_mcp.domain.common.result import (
    Err,
    Ok,
    Result,
    is_err,
    is_ok,
    unwrap,
    unwrap_err,
)

__all__ = [
    "AgentNotAllowlisted",
    "CapabilityDenied",
    "DatabaseFault",
    "DomainError",
    "Err",
    "InvariantViolation",
    "Ok",
    "PassportInvalid",
    "PassportMissing",
    "PolicyStoreFault",
    "Result",
    "SqlParseFault",
    "StatementClassDenied",
    "ToolInputInvalid",
    "is_err",
    "is_ok",
    "unwrap",
    "unwrap_err",
]
