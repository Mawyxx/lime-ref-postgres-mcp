"""SQL guard fixture-driven tests (Grd-1..7)."""

from __future__ import annotations

import pytest
from tests.unit.domain.sql.builders import (
    DDL_DROP,
    DML_MODIFYING_CTE,
    EXPLAIN_ANALYZE_DML,
    READ_PLAIN,
    TOP_LEVEL_INSERT,
    TXN_CONTROL,
    UNKNOWN_MULTI,
    make_sql_analysis,
)

from lime_ref_postgres_mcp.domain.access.capability import ToolCapability
from lime_ref_postgres_mcp.domain.access.policy import (
    REASON_CAPABILITY_DENIED,
    REASON_STATEMENT_CLASS_DENIED,
)
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName
from lime_ref_postgres_mcp.domain.common.errors import StatementClassDenied
from lime_ref_postgres_mcp.domain.sql.guard import guard
from lime_ref_postgres_mcp.domain.sql.types import SqlStatementClass

READ_PERMS = frozenset({ToolCapability.READ_DATA, ToolCapability.READ_SCHEMA})
WRITE_PERMS = frozenset(
    {ToolCapability.READ_DATA, ToolCapability.READ_SCHEMA, ToolCapability.WRITE_DATA}
)


def test_grd1_readonly_read_allowed() -> None:
    d = guard(ToolName.EXECUTE_READONLY_QUERY, READ_PLAIN, READ_PERMS)
    assert d.allowed is True
    assert d.statement_class == SqlStatementClass.READ
    assert d.reason_code is None
    assert d.to_denied_error() is None


def test_grd2_readonly_dml_cte_denied() -> None:
    d = guard(ToolName.EXECUTE_READONLY_QUERY, DML_MODIFYING_CTE, READ_PERMS)
    assert d.allowed is False
    assert d.reason_code == REASON_STATEMENT_CLASS_DENIED
    err = d.to_denied_error()
    assert isinstance(err, StatementClassDenied)


def test_grd3_write_insert_allowed() -> None:
    d = guard(ToolName.EXECUTE_WRITE_QUERY, TOP_LEVEL_INSERT, WRITE_PERMS)
    assert d.allowed is True
    assert d.required_capability == ToolCapability.WRITE_DATA


def test_grd4_write_ddl_denied() -> None:
    d = guard(ToolName.EXECUTE_WRITE_QUERY, DDL_DROP, WRITE_PERMS)
    assert d.allowed is False
    assert d.reason_code == REASON_STATEMENT_CLASS_DENIED
    assert d.statement_class == SqlStatementClass.DDL


def test_grd5_write_select_modifying_cte_denied() -> None:
    d = guard(ToolName.EXECUTE_WRITE_QUERY, DML_MODIFYING_CTE, WRITE_PERMS)
    assert d.allowed is False
    assert d.reason_code == REASON_STATEMENT_CLASS_DENIED


def test_grd6_multi_txn_unknown_denied() -> None:
    for fixture in (UNKNOWN_MULTI, TXN_CONTROL):
        d = guard(ToolName.EXECUTE_READONLY_QUERY, fixture, READ_PERMS)
        assert d.allowed is False
        assert d.reason_code == REASON_STATEMENT_CLASS_DENIED


def test_grd7_explain_analyze_dml_denied() -> None:
    d = guard(ToolName.EXPLAIN_QUERY_PLAN, EXPLAIN_ANALYZE_DML, READ_PERMS)
    assert d.allowed is False
    assert d.reason_code == REASON_STATEMENT_CLASS_DENIED


def test_non_raw_sql_tool_fail_closed() -> None:
    d = guard(ToolName.LIST_SCHEMAS, READ_PLAIN, READ_PERMS)
    assert d.allowed is False
    assert d.reason_code == REASON_STATEMENT_CLASS_DENIED


def test_readonly_missing_capability() -> None:
    d = guard(ToolName.EXECUTE_READONLY_QUERY, READ_PLAIN, frozenset())
    assert d.allowed is False
    assert d.reason_code == REASON_CAPABILITY_DENIED


def test_write_missing_capability() -> None:
    d = guard(ToolName.EXECUTE_WRITE_QUERY, TOP_LEVEL_INSERT, READ_PERMS)
    assert d.allowed is False
    assert d.reason_code == REASON_CAPABILITY_DENIED


def test_explain_plain_read_allowed() -> None:
    d = guard(ToolName.EXPLAIN_QUERY_PLAN, READ_PLAIN, READ_PERMS)
    assert d.allowed is True


def test_write_top_level_kind_but_non_dml_class_denied() -> None:
    analysis = make_sql_analysis(
        statement_class=SqlStatementClass.DDL,
        top_level_kind="InsertStmt",
    )
    d = guard(ToolName.EXECUTE_WRITE_QUERY, analysis, WRITE_PERMS)
    assert d.allowed is False
    assert d.reason_code == REASON_STATEMENT_CLASS_DENIED


def test_write_update_delete_allowed() -> None:
    for kind in ("UpdateStmt", "DeleteStmt"):
        analysis = make_sql_analysis(
            statement_class=SqlStatementClass.DML,
            top_level_kind=kind,
        )
        d = guard(ToolName.EXECUTE_WRITE_QUERY, analysis, WRITE_PERMS)
        assert d.allowed is True


def test_guard_decision_frozen() -> None:
    d = guard(ToolName.EXECUTE_READONLY_QUERY, READ_PLAIN, READ_PERMS)
    with pytest.raises(AttributeError):
        d.allowed = False  # type: ignore[misc]
