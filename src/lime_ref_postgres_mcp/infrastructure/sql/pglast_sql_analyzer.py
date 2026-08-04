"""PglastSqlAnalyzer — libpg_query AST → domain SqlAnalysis."""

from __future__ import annotations

from pglast import parse_sql
from pglast.parser import ParseError

from lime_ref_postgres_mcp.domain.common.errors import SqlParseFault
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, Result
from lime_ref_postgres_mcp.domain.sql.analysis import SqlAnalysis
from lime_ref_postgres_mcp.infrastructure.sql.ast_classify import resolve_statement_class
from lime_ref_postgres_mcp.infrastructure.sql.ast_walk import walk_statements


class PglastSqlAnalyzer:
    """Infrastructure adapter: sync CPU-bound SQL parse + classify."""

    def analyze(self, sql: str) -> Result[SqlAnalysis, SqlParseFault]:
        if not sql or not sql.strip():
            return Err(
                SqlParseFault(
                    invariant_id="sql.parse_fault",
                    message="empty SQL input",
                    context={"parse_error": "empty input"},
                )
            )
        try:
            raw_statements = parse_sql(sql)
        except ParseError:
            return Err(
                SqlParseFault(
                    invariant_id="sql.parse_fault",
                    message="SQL parse failed",
                    context={"parse_error": "syntax error"},
                )
            )
        walk = walk_statements(raw_statements)
        statement_class = resolve_statement_class(walk)
        return Ok(
            SqlAnalysis(
                statement_class=statement_class,
                statement_count=walk.statement_count,
                top_level_kind=walk.top_level_kind,
                has_modifying_cte=walk.has_modifying_cte,
                has_txn_control=walk.has_txn_control,
                is_explain_analyze=walk.is_explain_analyze,
            )
        )


__all__ = ["PglastSqlAnalyzer"]
