"""InvokeAgentToolService — thin orchestration facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import assert_never

from lime_ref_postgres_mcp.application.commands.invoke_agent_tool import InvokeAgentToolCommand
from lime_ref_postgres_mcp.application.context.agent_reply import AgentReply
from lime_ref_postgres_mcp.application.ports.database import DatabaseGateway
from lime_ref_postgres_mcp.application.services.authorize_tool import (
    AuthorizeToolService,
    AuthzError,
)
from lime_ref_postgres_mcp.application.services.emit_agent_action import EmitAgentActionService
from lime_ref_postgres_mcp.application.services.establish_request_context import (
    EstablishRequestContextService,
    PreAuthError,
)
from lime_ref_postgres_mcp.application.services.run_execution_plan import run_execution_plan
from lime_ref_postgres_mcp.domain.access.policy import (
    REASON_CAPABILITY_DENIED,
    REASON_DATABASE_FAULT,
    REASON_SQL_PARSE_FAULT,
    REASON_STATEMENT_CLASS_DENIED,
    REASON_TOOL_INPUT_INVALID,
)
from lime_ref_postgres_mcp.domain.auditing.event_outcome import EventOutcome
from lime_ref_postgres_mcp.domain.common.errors import (
    CapabilityDenied,
    DatabaseFault,
    SqlParseFault,
    StatementClassDenied,
    ToolInputInvalid,
)
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, Result


def _authz_to_reply_and_outcome(error: AuthzError) -> tuple[AgentReply, EventOutcome]:
    if isinstance(error, CapabilityDenied):
        raw_missing = error.context.get("missing", ())
        if isinstance(raw_missing, (list, tuple, set)):
            missing_caps = tuple(str(m) for m in raw_missing)
        else:
            missing_caps = ()
        return (
            AgentReply(
                status="denied",
                payload={"error": error.message, "code": error.invariant_id},
            ),
            EventOutcome(
                reason_code=REASON_CAPABILITY_DENIED,
                missing_capabilities=missing_caps,
            ),
        )
    if isinstance(error, StatementClassDenied):
        stmt = error.context.get("statement_class")
        return (
            AgentReply(
                status="denied",
                payload={"error": error.message, "code": error.invariant_id},
            ),
            EventOutcome(
                reason_code=REASON_STATEMENT_CLASS_DENIED,
                statement_class=str(stmt) if stmt is not None else None,
            ),
        )
    if isinstance(error, SqlParseFault):
        return (
            AgentReply(status="denied", payload={"error": "SQL could not be parsed"}),
            EventOutcome(reason_code=REASON_SQL_PARSE_FAULT),
        )
    if isinstance(error, ToolInputInvalid):
        return (
            AgentReply(
                status="denied",
                payload={"error": error.message, "code": error.invariant_id},
            ),
            EventOutcome(reason_code=REASON_TOOL_INPUT_INVALID),
        )
    assert_never(error)


@dataclass(frozen=True, slots=True)
class InvokeAgentToolService:
    establish: EstablishRequestContextService
    authorize: AuthorizeToolService
    emit: EmitAgentActionService
    database: DatabaseGateway

    async def execute(self, cmd: InvokeAgentToolCommand) -> Result[AgentReply, PreAuthError]:
        established = await self.establish.execute(cmd)
        if isinstance(established, Err):
            return Err(established.error)
        ctx = established.value
        authz = self.authorize.execute(ctx)
        if isinstance(authz, Err):
            reply, outcome = _authz_to_reply_and_outcome(authz.error)
            await self.emit.emit(ctx, "denied", outcome)
            return Ok(reply)
        db_result = await run_execution_plan(self.database, authz.value)
        if isinstance(db_result, Err):
            fault: DatabaseFault = db_result.error
            reply = AgentReply(
                status="error",
                payload={"error": fault.message, "code": fault.invariant_id},
            )
            await self.emit.emit(ctx, "error", EventOutcome(reason_code=REASON_DATABASE_FAULT))
            return Ok(reply)
        payload = db_result.value
        reply = AgentReply(status="ok", payload=payload.payload)
        await self.emit.emit(
            ctx,
            "ok",
            EventOutcome(rows_count=payload.rows_count, affected_rows=payload.affected_rows),
        )
        return Ok(reply)


__all__ = ["InvokeAgentToolService", "_authz_to_reply_and_outcome"]
