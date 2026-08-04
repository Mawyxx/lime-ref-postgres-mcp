"""SqlAnalysis VO tests."""

from __future__ import annotations

import pytest
from tests.unit.domain.sql.builders import READ_PLAIN, make_sql_analysis

from lime_ref_postgres_mcp.domain.sql.types import STATEMENT_CLASS_CAPABILITY, SqlStatementClass


def test_sql_analysis_fields() -> None:
    a = READ_PLAIN
    assert a.statement_class == SqlStatementClass.READ
    assert a.statement_count == 1
    assert a.top_level_kind == "SelectStmt"
    assert a.has_modifying_cte is False
    assert a.has_txn_control is False
    assert a.is_explain_analyze is False


def test_sql_analysis_frozen() -> None:
    a = make_sql_analysis()
    with pytest.raises(AttributeError):
        a.statement_count = 9  # type: ignore[misc]


def test_statement_class_capability_map() -> None:
    assert STATEMENT_CLASS_CAPABILITY[SqlStatementClass.READ].value == "READ_DATA"
    assert STATEMENT_CLASS_CAPABILITY[SqlStatementClass.UNKNOWN] is None
