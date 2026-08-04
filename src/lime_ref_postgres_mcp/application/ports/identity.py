"""PassportVerifier port — LIME JWT verify (async I/O in adapter)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from lime_ref_postgres_mcp.domain.agent.agent_id import AgentId
from lime_ref_postgres_mcp.domain.common.errors import PassportInvalid, PassportMissing
from lime_ref_postgres_mcp.domain.common.result import Result


@dataclass(frozen=True, slots=True)
class PassportClaims:
    """Verified passport claims — never carries raw JWT."""

    agent_id: AgentId
    domain: str | None = None
    aud: str | None = None
    exp: datetime | None = None


class PassportVerifier(Protocol):
    async def verify(
        self, bearer_token: str
    ) -> Result[PassportClaims, PassportMissing | PassportInvalid]: ...


__all__ = ["PassportClaims", "PassportVerifier"]
