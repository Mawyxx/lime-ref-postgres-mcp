"""Fake SqlAnalyzer — canned SqlAnalysis / SqlParseFault."""

from __future__ import annotations

from lime_ref_postgres_mcp.domain.common.errors import SqlParseFault
from lime_ref_postgres_mcp.domain.common.result import Ok, Result
from lime_ref_postgres_mcp.domain.sql.analysis import SqlAnalysis
from lime_ref_postgres_mcp.domain.sql.types import SqlStatementClass


class FakeSqlAnalyzer:
    def __init__(self) -> None:
        self._by_sql: dict[str, Result[SqlAnalysis, SqlParseFault]] = {}
        self.default = Ok(
            SqlAnalysis(
                statement_class=SqlStatementClass.READ,
                statement_count=1,
                top_level_kind="SelectStmt",
                has_modifying_cte=False,
                has_txn_control=False,
                is_explain_analyze=False,
            )
        )

    def set_result(self, sql: str, result: Result[SqlAnalysis, SqlParseFault]) -> None:
        self._by_sql[sql] = result

    def set_analysis(self, sql: str, analysis: SqlAnalysis) -> None:
        self._by_sql[sql] = Ok(analysis)

    def analyze(self, sql: str) -> Result[SqlAnalysis, SqlParseFault]:
        if sql in self._by_sql:
            return self._by_sql[sql]
        return self.default


__all__ = ["FakeSqlAnalyzer"]
