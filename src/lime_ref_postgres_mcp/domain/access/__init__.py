"""Access / policy / capability domain."""

from lime_ref_postgres_mcp.domain.access.authorized_agent import AuthorizedAgent
from lime_ref_postgres_mcp.domain.access.capability import ToolCapability
from lime_ref_postgres_mcp.domain.access.capability_check import (
    CapabilityDecision,
    capability_check,
)
from lime_ref_postgres_mcp.domain.access.policy import (
    DEFAULT_PERMISSIONS,
    REASON_CAPABILITY_DENIED,
    REASON_DATABASE_FAULT,
    REASON_SQL_PARSE_FAULT,
    REASON_STATEMENT_CLASS_DENIED,
    REASON_TOOL_INPUT_INVALID,
    AgentPolicy,
    PolicyDocument,
)

__all__ = [
    "DEFAULT_PERMISSIONS",
    "REASON_CAPABILITY_DENIED",
    "REASON_DATABASE_FAULT",
    "REASON_SQL_PARSE_FAULT",
    "REASON_STATEMENT_CLASS_DENIED",
    "REASON_TOOL_INPUT_INVALID",
    "AgentPolicy",
    "AuthorizedAgent",
    "CapabilityDecision",
    "PolicyDocument",
    "ToolCapability",
    "capability_check",
]
