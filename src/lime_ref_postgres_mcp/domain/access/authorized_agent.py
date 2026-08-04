"""Authorized agent shape after passport + whitelist OK."""

from __future__ import annotations

from dataclasses import dataclass

from lime_ref_postgres_mcp.domain.access.capability import ToolCapability
from lime_ref_postgres_mcp.domain.access.policy import AgentPolicy
from lime_ref_postgres_mcp.domain.agent.agent_id import AgentId


@dataclass(frozen=True, slots=True)
class AuthorizedAgent:
    """Post-whitelist identity + permissions (no passport verify here)."""

    agent_id: AgentId
    permissions: frozenset[ToolCapability]
    domain: str | None = None

    @classmethod
    def from_policy(cls, policy: AgentPolicy, *, domain: str | None = None) -> AuthorizedAgent:
        return cls(
            agent_id=policy.agent_id,
            permissions=policy.permissions,
            domain=domain,
        )


__all__ = ["AuthorizedAgent"]
