"""SqlAnalyzer port import smoke test."""

from __future__ import annotations

from lime_ref_postgres_mcp.application.ports.sql_analyzer import SqlAnalyzer
from lime_ref_postgres_mcp.domain.common.result import is_ok, unwrap
from lime_ref_postgres_mcp.infrastructure.sql.pglast_sql_analyzer import PglastSqlAnalyzer


def test_pglast_implements_sql_analyzer_protocol() -> None:
    analyzer: SqlAnalyzer = PglastSqlAnalyzer()
    result = analyzer.analyze("SELECT 1")
    assert is_ok(result)
    assert unwrap(result).statement_class.value == "READ"
