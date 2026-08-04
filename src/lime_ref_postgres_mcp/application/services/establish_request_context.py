"""EstablishRequestContext — passport + whitelist → RequestContext (no emit)."""

from __future__ import annotations

from dataclasses import dataclass

from lime_ref_postgres_mcp.application.commands.invoke_agent_tool import InvokeAgentToolCommand
from lime_ref_postgres_mcp.application.context.request_context import PolicySnapshot, RequestContext
from lime_ref_postgres_mcp.application.ports.clock import Clock, IdGenerator
from lime_ref_postgres_mcp.application.ports.identity import PassportVerifier
from lime_ref_postgres_mcp.application.ports.policy import AgentPolicyStore
from lime_ref_postgres_mcp.bootstrap.observability import bind_context, log, metrics
from lime_ref_postgres_mcp.domain.access.authorized_agent import AuthorizedAgent
from lime_ref_postgres_mcp.domain.common.errors import (
    AgentNotAllowlisted,
    DomainError,
    PassportInvalid,
    PassportMissing,
    PolicyStoreFault,
)
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, Result

PreAuthError = PassportMissing | PassportInvalid | AgentNotAllowlisted | PolicyStoreFault


def _preauth_fail(error: DomainError) -> Err[PreAuthError]:
    code = str(error.context.get("reason_code") or error.invariant_id)
    log(
        "establish",
        "preauth.fail",
        level="WARNING",
        code=code,
        invariant_id=error.invariant_id,
    )
    metrics.inc("mcp_preauth_fail_total", code=code)
    return Err(error)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class EstablishRequestContextService:
    verifier: PassportVerifier
    policy_store: AgentPolicyStore
    clock: Clock
    ids: IdGenerator

    async def execute(self, cmd: InvokeAgentToolCommand) -> Result[RequestContext, PreAuthError]:
        request_id = cmd.request_id or self.ids.new_request_id()
        token = cmd.bearer_token
        if token is None or not token.strip():
            return _preauth_fail(
                PassportMissing(
                    invariant_id="identity.passport_missing",
                    message="Authorization Bearer token is missing",
                    context={},
                )
            )
        claims_result = await self.verifier.verify(token.strip())
        if isinstance(claims_result, Err):
            return _preauth_fail(claims_result.error)
        claims = claims_result.value
        policy_result = await self.policy_store.current()
        if isinstance(policy_result, Err):
            return _preauth_fail(policy_result.error)
        document = policy_result.value
        resolved = document.resolve(claims.agent_id)
        if isinstance(resolved, Err):
            return _preauth_fail(resolved.error)
        agent = AuthorizedAgent.from_policy(resolved.value, domain=claims.domain)
        now = self.clock.now_utc()
        bind_context(agent_id=str(agent.agent_id))
        log(
            "establish",
            "context.ok",
            request_id=request_id,
            agent_id=str(agent.agent_id),
            tool=cmd.tool.value,
        )
        return Ok(
            RequestContext(
                request_id=request_id,
                agent=agent,
                tool=cmd.tool,
                args=dict(cmd.args),
                started_at=now,
                policy=PolicySnapshot(document=document, loaded_at=now),
            )
        )


__all__ = ["EstablishRequestContextService", "PreAuthError"]
