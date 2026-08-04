"""Admin-surface MCP handlers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mcp.types import CallToolResult

from lime_ref_postgres_mcp.application.services.invoke_agent_tool import InvokeAgentToolService
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName
from lime_ref_postgres_mcp.presentation.mcp.handlers._invoke import invoke_tool


async def get_database_stats(
    invoke: InvokeAgentToolService,
    bearer_token: str | None,
    args: Mapping[str, Any],
    request_id: str,
) -> CallToolResult:
    return await invoke_tool(invoke, ToolName.GET_DATABASE_STATS, bearer_token, {}, request_id)


__all__ = ["get_database_stats"]
