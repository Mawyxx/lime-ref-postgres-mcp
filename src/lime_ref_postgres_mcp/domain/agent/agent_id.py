"""Agent identity value object (JWT ``sub`` after verify)."""

from __future__ import annotations

from dataclasses import dataclass

from lime_ref_postgres_mcp.domain.common.errors import InvariantViolation
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, Result


@dataclass(frozen=True, slots=True)
class AgentId:
    """Non-empty stripped agent identifier."""

    value: str

    @classmethod
    def parse(cls, raw: object) -> Result[AgentId, InvariantViolation]:
        if not isinstance(raw, str):
            return Err(
                InvariantViolation(
                    invariant_id="agent.id_invalid",
                    message="agent_id must be a string",
                    context={"type": type(raw).__name__},
                )
            )
        stripped = raw.strip()
        if not stripped:
            return Err(
                InvariantViolation(
                    invariant_id="agent.id_empty",
                    message="agent_id must be non-empty",
                    context={},
                )
            )
        return Ok(cls(value=stripped))

    def __str__(self) -> str:
        return self.value


__all__ = ["AgentId"]
