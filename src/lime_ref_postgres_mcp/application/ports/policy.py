"""AgentPolicyStore port — current policy snapshot."""

from __future__ import annotations

from typing import Protocol

from lime_ref_postgres_mcp.domain.access.policy import PolicyDocument
from lime_ref_postgres_mcp.domain.common.errors import PolicyStoreFault
from lime_ref_postgres_mcp.domain.common.result import Result


class AgentPolicyStore(Protocol):
    async def current(self) -> Result[PolicyDocument, PolicyStoreFault]: ...


__all__ = ["AgentPolicyStore"]
