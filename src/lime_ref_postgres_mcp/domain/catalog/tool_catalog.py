"""Tool catalog SSOT: ToolName → required ToolCapability."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Final

from lime_ref_postgres_mcp.domain.access.capability import ToolCapability


class ToolName(StrEnum):
    """MCP tool names (must match transport registration)."""

    LIST_SCHEMAS = "list_schemas"
    LIST_TABLES = "list_tables"
    GET_TABLE_SCHEMA = "get_table_schema"
    SELECT_ROWS = "select_rows"
    EXECUTE_READONLY_QUERY = "execute_readonly_query"
    EXPLAIN_QUERY_PLAN = "explain_query_plan"
    EXECUTE_WRITE_QUERY = "execute_write_query"
    GET_DATABASE_STATS = "get_database_stats"


REQUIRED_CAPABILITY: Final[Mapping[ToolName, ToolCapability]] = {
    ToolName.LIST_SCHEMAS: ToolCapability.READ_SCHEMA,
    ToolName.LIST_TABLES: ToolCapability.READ_SCHEMA,
    ToolName.GET_TABLE_SCHEMA: ToolCapability.READ_SCHEMA,
    ToolName.SELECT_ROWS: ToolCapability.READ_DATA,
    ToolName.EXECUTE_READONLY_QUERY: ToolCapability.READ_DATA,
    ToolName.EXPLAIN_QUERY_PLAN: ToolCapability.READ_DATA,
    ToolName.EXECUTE_WRITE_QUERY: ToolCapability.WRITE_DATA,
    ToolName.GET_DATABASE_STATS: ToolCapability.ADMIN,
}

RAW_SQL_TOOLS: Final[frozenset[ToolName]] = frozenset(
    {
        ToolName.EXECUTE_READONLY_QUERY,
        ToolName.EXPLAIN_QUERY_PLAN,
        ToolName.EXECUTE_WRITE_QUERY,
    }
)


def required_capability(tool: ToolName) -> ToolCapability:
    return REQUIRED_CAPABILITY[tool]


__all__ = [
    "RAW_SQL_TOOLS",
    "REQUIRED_CAPABILITY",
    "ToolName",
    "required_capability",
]
