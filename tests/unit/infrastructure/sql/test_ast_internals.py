"""Direct tests for ast_classify and ast_walk edge coverage."""

from __future__ import annotations

from pglast import parse_sql

from lime_ref_postgres_mcp.domain.sql.types import SqlStatementClass
from lime_ref_postgres_mcp.infrastructure.sql.ast_classify import resolve_statement_class
from lime_ref_postgres_mcp.infrastructure.sql.ast_walk import WalkResult, walk_statements


def test_walk_empty_statements() -> None:
    walk = walk_statements(())
    assert walk.statement_count == 0
    assert walk.top_level_kind == "Empty"
    assert resolve_statement_class(walk) == SqlStatementClass.UNKNOWN


def test_resolve_txn_only_unknown() -> None:
    walk = walk_statements(parse_sql("COMMIT"))
    assert walk.has_txn_control is True
    assert resolve_statement_class(walk) == SqlStatementClass.UNKNOWN


def test_resolve_no_categories_unknown() -> None:
    walk = WalkResult(
        statement_count=1,
        top_level_kind="VariableSetStmt",
        categories=frozenset(),
        has_modifying_cte=False,
        has_txn_control=False,
        is_explain_analyze=False,
        has_for_update=False,
        has_select_into=False,
    )
    assert resolve_statement_class(walk) == SqlStatementClass.UNKNOWN


def test_resolve_unknown_when_categories_unmapped() -> None:
    walk = WalkResult(
        statement_count=1,
        top_level_kind="CustomStmt",
        categories=frozenset({"NOTMAPPED"}),  # type: ignore[arg-type]
        has_modifying_cte=False,
        has_txn_control=False,
        is_explain_analyze=False,
        has_for_update=False,
        has_select_into=False,
    )
    assert resolve_statement_class(walk) == SqlStatementClass.UNKNOWN


def test_explain_without_analyze_flag() -> None:
    walk = walk_statements(parse_sql("EXPLAIN SELECT 1"))
    assert walk.is_explain_analyze is False
    assert resolve_statement_class(walk) == SqlStatementClass.READ


def test_read_only_cte_not_modifying() -> None:
    walk = walk_statements(parse_sql("WITH x AS (SELECT 1) SELECT * FROM x"))
    assert walk.has_modifying_cte is False


def test_has_modifying_cte_skips_none_ctequery() -> None:
    from lime_ref_postgres_mcp.infrastructure.sql.ast_walk import _has_modifying_cte

    class SelectStmt:
        pass

    root = SelectStmt()
    root.withClause = type("WithClause", (), {"ctes": (type("Cte", (), {"ctequery": None})(),)})()
    assert _has_modifying_cte(root) is False
