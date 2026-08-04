"""Fake PassportVerifier."""

from __future__ import annotations

from lime_ref_postgres_mcp.application.ports.identity import PassportClaims
from lime_ref_postgres_mcp.domain.agent.agent_id import AgentId
from lime_ref_postgres_mcp.domain.common.errors import PassportInvalid, PassportMissing
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, Result, unwrap


class FakePassportVerifier:
    def __init__(
        self,
        *,
        claims_by_token: dict[str, PassportClaims] | None = None,
        default_agent_id: str = "agent_ok",
    ) -> None:
        self._claims = claims_by_token or {}
        self._default = unwrap(AgentId.parse(default_agent_id))
        self.calls: list[str] = []

    def register(self, token: str, claims: PassportClaims) -> None:
        self._claims[token] = claims

    async def verify(
        self, bearer_token: str
    ) -> Result[PassportClaims, PassportMissing | PassportInvalid]:
        self.calls.append(bearer_token)
        if bearer_token in self._claims:
            return Ok(self._claims[bearer_token])
        if bearer_token == "bad":
            return Err(
                PassportInvalid(
                    invariant_id="identity.passport_invalid",
                    message="invalid passport",
                    context={},
                )
            )
        return Ok(PassportClaims(agent_id=self._default, domain="example.com"))


__all__ = ["FakePassportVerifier"]
