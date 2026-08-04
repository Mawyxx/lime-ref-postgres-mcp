"""Schema-surface MCP handlers (READ_SCHEMA)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mcp.types import CallToolResult

from lime_ref_postgres_mcp.application.services.invoke_agent_tool import InvokeAgentToolService
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName
from lime_ref_postgres_mcp.presentation.mcp.handlers._invoke import invoke_tool


async def list_schemas(
    invoke: InvokeAgentToolService,
    bearer_token: str | None,
    args: Mapping[str, Any],
    request_id: str,
) -> CallToolResult:
    return await invoke_tool(invoke, ToolName.LIST_SCHEMAS, bearer_token, {}, request_id)


async def list_tables(
    invoke: InvokeAgentToolService,
    bearer_token: str | None,
    args: Mapping[str, Any],
    request_id: str,
) -> CallToolResult:
    return await invoke_tool(invoke, ToolName.LIST_TABLES, bearer_token, dict(args), request_id)


async def get_table_schema(
    invoke: InvokeAgentToolService,
    bearer_token: str | None,
    args: Mapping[str, Any],
    request_id: str,
) -> CallToolResult:
    return await invoke_tool(
        invoke, ToolName.GET_TABLE_SCHEMA, bearer_token, dict(args), request_id
    )


__all__ = ["get_table_schema", "list_schemas", "list_tables"]
