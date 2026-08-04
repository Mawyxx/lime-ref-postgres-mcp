"""Capability check: tool required cap ∈ agent permissions."""

from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass

from lime_ref_postgres_mcp.domain.access.capability import ToolCapability
from lime_ref_postgres_mcp.domain.access.policy import REASON_CAPABILITY_DENIED
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName, required_capability
from lime_ref_postgres_mcp.domain.common.errors import CapabilityDenied


@dataclass(frozen=True, slots=True)
class CapabilityDecision:
    """Pure allow/deny for tool capability gate."""

    allowed: bool
    required: ToolCapability
    missing: frozenset[ToolCapability]
    reason_code: str | None = None

    def to_denied_error(self) -> CapabilityDenied | None:
        if self.allowed:
            return None
        return CapabilityDenied(
            invariant_id="access.capability_denied",
            message="agent lacks required capability for tool",
            context={
                "required": self.required.value,
                "missing": tuple(sorted(c.value for c in self.missing)),
                "reason_code": self.reason_code or REASON_CAPABILITY_DENIED,
            },
        )


def capability_check(
    tool: ToolName,
    permissions: Set[ToolCapability],
) -> CapabilityDecision:
    required = required_capability(tool)
    if required in permissions:
        return CapabilityDecision(
            allowed=True,
            required=required,
            missing=frozenset(),
            reason_code=None,
        )
    return CapabilityDecision(
        allowed=False,
        required=required,
        missing=frozenset({required}),
        reason_code=REASON_CAPABILITY_DENIED,
    )


__all__ = ["CapabilityDecision", "capability_check"]
