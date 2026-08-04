"""MCP Tool schemas — ToolName + Authorize arg keys (SSOT)."""

from __future__ import annotations

from mcp.types import Tool

from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName

_OBJECT = {"type": "object"}

TOOL_SPECS: tuple[Tool, ...] = (
    Tool(
        name=ToolName.LIST_SCHEMAS.value,
        description="List non-system PostgreSQL schemas.",
        input_schema={**_OBJECT, "properties": {}, "additionalProperties": False},
    ),
    Tool(
        name=ToolName.LIST_TABLES.value,
        description="List tables in a schema.",
        input_schema={
            **_OBJECT,
            "properties": {"schema": {"type": "string"}},
            "required": ["schema"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name=ToolName.GET_TABLE_SCHEMA.value,
        description="Describe columns of a table.",
        input_schema={
            **_OBJECT,
            "properties": {
                "schema": {"type": "string"},
                "table": {"type": "string"},
            },
            "required": ["schema", "table"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name=ToolName.SELECT_ROWS.value,
        description="Select rows from a table (parameterized).",
        input_schema={
            **_OBJECT,
            "properties": {
                "schema": {"type": "string"},
                "table": {"type": "string"},
                "columns": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer"},
                "offset": {"type": "integer"},
            },
            "required": ["schema", "table"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name=ToolName.EXECUTE_READONLY_QUERY.value,
        description="Execute a single READ-class SQL statement.",
        input_schema={
            **_OBJECT,
            "properties": {
                "sql": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["sql"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name=ToolName.EXPLAIN_QUERY_PLAN.value,
        description="EXPLAIN a single SQL statement.",
        input_schema={
            **_OBJECT,
            "properties": {"sql": {"type": "string"}},
            "required": ["sql"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name=ToolName.EXECUTE_WRITE_QUERY.value,
        description="Execute a single DML write statement.",
        input_schema={
            **_OBJECT,
            "properties": {
                "sql": {"type": "string"},
                "target_table": {"type": "string"},
            },
            "required": ["sql"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name=ToolName.GET_DATABASE_STATS.value,
        description="Database size / admin stats.",
        input_schema={**_OBJECT, "properties": {}, "additionalProperties": False},
    ),
)


def list_tool_specs() -> list[Tool]:
    return list(TOOL_SPECS)


__all__ = ["TOOL_SPECS", "list_tool_specs"]
