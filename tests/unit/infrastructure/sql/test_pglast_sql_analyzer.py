"""PglastSqlAnalyzer unit tests (Ana-1..5)."""

from __future__ import annotations

import pytest

from lime_ref_postgres_mcp.domain.common.errors import SqlParseFault
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, unwrap, unwrap_err
from lime_ref_postgres_mcp.domain.sql.types import SqlStatementClass
from lime_ref_postgres_mcp.infrastructure.sql.pglast_sql_analyzer import PglastSqlAnalyzer


@pytest.fixture
def analyzer() -> PglastSqlAnalyzer:
    return PglastSqlAnalyzer()


def test_ana1_plain_select_read(analyzer: PglastSqlAnalyzer) -> None:
    result = analyzer.analyze("SELECT 1")
    assert isinstance(result, Ok)
    analysis = unwrap(result)
    assert analysis.statement_class == SqlStatementClass.READ
    assert analysis.statement_count == 1
    assert analysis.top_level_kind == "SelectStmt"
    assert analysis.has_modifying_cte is False
    assert analysis.has_txn_control is False
    assert analysis.is_explain_analyze is False


def test_ana2_invalid_syntax(analyzer: PglastSqlAnalyzer) -> None:
    result = analyzer.analyze("SELEC 1")
    assert isinstance(result, Err)
    err = unwrap_err(result)
    assert isinstance(err, SqlParseFault)
    assert err.invariant_id == "sql.parse_fault"
    assert "parse_error" in err.context
    assert "sql" not in str(err.context).lower() or "SELEC" not in str(err.context)


def test_ana3_empty_string(analyzer: PglastSqlAnalyzer) -> None:
    result = analyzer.analyze("   ")
    assert isinstance(result, Err)
    assert isinstance(unwrap_err(result), SqlParseFault)


def test_ana4_insert_dml(analyzer: PglastSqlAnalyzer) -> None:
    result = analyzer.analyze("INSERT INTO t VALUES (1)")
    analysis = unwrap(result)
    assert analysis.statement_class == SqlStatementClass.DML
    assert analysis.top_level_kind == "InsertStmt"


def test_ana5_txn_unknown(analyzer: PglastSqlAnalyzer) -> None:
    result = analyzer.analyze("BEGIN; SELECT 1")
    analysis = unwrap(result)
    assert analysis.statement_class == SqlStatementClass.UNKNOWN
    assert analysis.has_txn_control is True


def test_parse_fault_no_raw_sql_in_context(analyzer: PglastSqlAnalyzer) -> None:
    err = unwrap_err(analyzer.analyze("SELEC 1"))
    assert err.context["parse_error"] == "syntax error"
    assert "SELEC" not in str(err.context)
