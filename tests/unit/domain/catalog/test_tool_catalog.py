"""Tool catalog SSOT tests."""

from __future__ import annotations

import pytest

from lime_ref_postgres_mcp.domain.access.capability import ToolCapability
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import (
    RAW_SQL_TOOLS,
    REQUIRED_CAPABILITY,
    ToolName,
    required_capability,
)

# Cat-1: exact PRD §6.3 / TDD §5.4 table
EXPECTED: dict[ToolName, ToolCapability] = {
    ToolName.LIST_SCHEMAS: ToolCapability.READ_SCHEMA,
    ToolName.LIST_TABLES: ToolCapability.READ_SCHEMA,
    ToolName.GET_TABLE_SCHEMA: ToolCapability.READ_SCHEMA,
    ToolName.SELECT_ROWS: ToolCapability.READ_DATA,
    ToolName.EXECUTE_READONLY_QUERY: ToolCapability.READ_DATA,
    ToolName.EXPLAIN_QUERY_PLAN: ToolCapability.READ_DATA,
    ToolName.EXECUTE_WRITE_QUERY: ToolCapability.WRITE_DATA,
    ToolName.GET_DATABASE_STATS: ToolCapability.ADMIN,
}


@pytest.mark.parametrize("tool,cap", list(EXPECTED.items()), ids=[t.value for t in EXPECTED])
def test_catalog_required_capability(tool: ToolName, cap: ToolCapability) -> None:
    assert required_capability(tool) == cap
    assert REQUIRED_CAPABILITY[tool] == cap


def test_catalog_covers_all_tool_names() -> None:
    assert set(REQUIRED_CAPABILITY) == set(ToolName)


def test_raw_sql_tools() -> None:
    assert RAW_SQL_TOOLS == frozenset(
        {
            ToolName.EXECUTE_READONLY_QUERY,
            ToolName.EXPLAIN_QUERY_PLAN,
            ToolName.EXECUTE_WRITE_QUERY,
        }
    )
