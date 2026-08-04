"""Map Invoke Result → MCP CallToolResult (never raise MCPError for domain outcomes)."""

from __future__ import annotations

import json

from mcp.types import CallToolResult, TextContent

from lime_ref_postgres_mcp.application.context.agent_reply import AgentReply
from lime_ref_postgres_mcp.application.services.establish_request_context import PreAuthError
from lime_ref_postgres_mcp.domain.common.result import Ok, Result


def map_to_mcp(result: Result[AgentReply, PreAuthError]) -> CallToolResult:
    """Wire envelope ``{"status","payload"}``; ``is_error`` when status != ok."""
    if isinstance(result, Ok):
        reply = result.value
        envelope = {"status": reply.status, "payload": reply.payload}
        is_error = reply.status != "ok"
    else:
        error = result.error
        envelope = {
            "status": "error",
            "payload": {"error": error.message, "code": error.invariant_id},
        }
        is_error = True
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(envelope, default=str))],
        is_error=is_error,
    )


__all__ = ["map_to_mcp"]
