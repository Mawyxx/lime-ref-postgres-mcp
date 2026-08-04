"""Tool specs SSOT tests."""

from __future__ import annotations

from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName
from lime_ref_postgres_mcp.presentation.mcp.tool_specs import TOOL_SPECS, list_tool_specs


def test_exactly_eight_tools() -> None:
    specs = list_tool_specs()
    assert len(specs) == 8
    assert len(TOOL_SPECS) == 8
    names = {t.name for t in specs}
    assert names == {t.value for t in ToolName}


def test_authorize_arg_keys_present() -> None:
    by_name = {t.name: t for t in TOOL_SPECS}
    assert "schema" in by_name[ToolName.LIST_TABLES.value].input_schema["properties"]
    assert "table" in by_name[ToolName.GET_TABLE_SCHEMA.value].input_schema["properties"]
    assert "sql" in by_name[ToolName.EXECUTE_READONLY_QUERY.value].input_schema["properties"]
    assert "schema_name" not in json_props(by_name[ToolName.LIST_TABLES.value])
    assert "sql_query" not in json_props(by_name[ToolName.EXECUTE_READONLY_QUERY.value])


def json_props(tool: object) -> set[str]:
    schema = tool.input_schema  # type: ignore[attr-defined]
    return set(schema.get("properties", {}))
