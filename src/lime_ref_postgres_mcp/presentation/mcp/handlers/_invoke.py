"""Shared invoke path for all MCP tool handlers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mcp.types import CallToolResult

from lime_ref_postgres_mcp.application.commands.invoke_agent_tool import InvokeAgentToolCommand
from lime_ref_postgres_mcp.application.services.invoke_agent_tool import InvokeAgentToolService
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName
from lime_ref_postgres_mcp.presentation.mcp.error_map import map_to_mcp


async def invoke_tool(
    invoke: InvokeAgentToolService,
    tool: ToolName,
    bearer_token: str | None,
    args: Mapping[str, Any],
    request_id: str,
) -> CallToolResult:
    cmd = InvokeAgentToolCommand(
        bearer_token=bearer_token,
        tool=tool,
        args=args,
        request_id=request_id,
    )
    result = await invoke.execute(cmd)
    return map_to_mcp(result)


__all__ = ["invoke_tool"]
