"""SqlAnalysis fixture builders for guard unit tests (no pglast)."""

from __future__ import annotations

from lime_ref_postgres_mcp.domain.sql.analysis import SqlAnalysis
from lime_ref_postgres_mcp.domain.sql.types import SqlStatementClass


def make_sql_analysis(
    *,
    statement_class: SqlStatementClass = SqlStatementClass.READ,
    statement_count: int = 1,
    top_level_kind: str = "SelectStmt",
    has_modifying_cte: bool = False,
    has_txn_control: bool = False,
    is_explain_analyze: bool = False,
) -> SqlAnalysis:
    return SqlAnalysis(
        statement_class=statement_class,
        statement_count=statement_count,
        top_level_kind=top_level_kind,
        has_modifying_cte=has_modifying_cte,
        has_txn_control=has_txn_control,
        is_explain_analyze=is_explain_analyze,
    )


READ_PLAIN = make_sql_analysis()

DML_MODIFYING_CTE = make_sql_analysis(
    statement_class=SqlStatementClass.DML,
    top_level_kind="SelectStmt",
    has_modifying_cte=True,
)

TOP_LEVEL_INSERT = make_sql_analysis(
    statement_class=SqlStatementClass.DML,
    top_level_kind="InsertStmt",
)

DDL_DROP = make_sql_analysis(
    statement_class=SqlStatementClass.DDL,
    top_level_kind="DropStmt",
)

UNKNOWN_MULTI = make_sql_analysis(
    statement_class=SqlStatementClass.UNKNOWN,
    statement_count=2,
    top_level_kind="SelectStmt",
)

TXN_CONTROL = make_sql_analysis(
    statement_class=SqlStatementClass.UNKNOWN,
    top_level_kind="TransactionStmt",
    has_txn_control=True,
)

EXPLAIN_ANALYZE_DML = make_sql_analysis(
    statement_class=SqlStatementClass.DML,
    top_level_kind="ExplainStmt",
    is_explain_analyze=True,
)

__all__ = [
    "DDL_DROP",
    "DML_MODIFYING_CTE",
    "EXPLAIN_ANALYZE_DML",
    "READ_PLAIN",
    "TOP_LEVEL_INSERT",
    "TXN_CONTROL",
    "UNKNOWN_MULTI",
    "make_sql_analysis",
]
