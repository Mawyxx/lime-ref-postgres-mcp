"""Data-surface MCP handlers (READ_DATA / WRITE_DATA)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mcp.types import CallToolResult

from lime_ref_postgres_mcp.application.services.invoke_agent_tool import InvokeAgentToolService
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName
from lime_ref_postgres_mcp.presentation.mcp.handlers._invoke import invoke_tool


async def select_rows(
    invoke: InvokeAgentToolService,
    bearer_token: str | None,
    args: Mapping[str, Any],
    request_id: str,
) -> CallToolResult:
    return await invoke_tool(invoke, ToolName.SELECT_ROWS, bearer_token, dict(args), request_id)


async def execute_readonly_query(
    invoke: InvokeAgentToolService,
    bearer_token: str | None,
    args: Mapping[str, Any],
    request_id: str,
) -> CallToolResult:
    return await invoke_tool(
        invoke, ToolName.EXECUTE_READONLY_QUERY, bearer_token, dict(args), request_id
    )


async def explain_query_plan(
    invoke: InvokeAgentToolService,
    bearer_token: str | None,
    args: Mapping[str, Any],
    request_id: str,
) -> CallToolResult:
    return await invoke_tool(
        invoke, ToolName.EXPLAIN_QUERY_PLAN, bearer_token, dict(args), request_id
    )


async def execute_write_query(
    invoke: InvokeAgentToolService,
    bearer_token: str | None,
    args: Mapping[str, Any],
    request_id: str,
) -> CallToolResult:
    return await invoke_tool(
        invoke, ToolName.EXECUTE_WRITE_QUERY, bearer_token, dict(args), request_id
    )


__all__ = [
    "execute_readonly_query",
    "execute_write_query",
    "explain_query_plan",
    "select_rows",
]
