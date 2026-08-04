"""Named domain errors for the agent/tool path (Prime A10)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class DomainError(Exception):
    """Base typed failure for authorized-path / domain outcomes."""

    invariant_id: str
    message: str
    context: Mapping[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.invariant_id}: {self.message}"


@dataclass(frozen=True, slots=True)
class InvariantViolation(DomainError):
    """Invalid VO / policy mapping / domain invariant breach."""


@dataclass(frozen=True, slots=True)
class AgentNotAllowlisted(DomainError):
    """agent_id not present in PolicyDocument.agents (pre-auth: no event)."""


@dataclass(frozen=True, slots=True)
class CapabilityDenied(DomainError):
    """Required ToolCapability missing from agent permissions."""


@dataclass(frozen=True, slots=True)
class StatementClassDenied(DomainError):
    """SQL statement class not allowed for the tool / permissions."""


@dataclass(frozen=True, slots=True)
class ToolInputInvalid(DomainError):
    """Tool arguments failed validation after authorization."""


@dataclass(frozen=True, slots=True)
class PassportMissing(DomainError):
    """Authorization Bearer header absent (pre-auth: no event)."""


@dataclass(frozen=True, slots=True)
class PassportInvalid(DomainError):
    """Passport verify / claims failed (pre-auth: no event)."""


@dataclass(frozen=True, slots=True)
class DatabaseFault(DomainError):
    """Postgres fault with masked safe message for the agent."""


@dataclass(frozen=True, slots=True)
class PolicyStoreFault(DomainError):
    """Policy config could not be loaded (process/health path)."""


@dataclass(frozen=True, slots=True)
class SqlParseFault(DomainError):
    """SQL AST parse failed (P1b analyzer)."""


__all__ = [
    "AgentNotAllowlisted",
    "CapabilityDenied",
    "DatabaseFault",
    "DomainError",
    "InvariantViolation",
    "PassportInvalid",
    "PassportMissing",
    "PolicyStoreFault",
    "SqlParseFault",
    "StatementClassDenied",
    "ToolInputInvalid",
]
