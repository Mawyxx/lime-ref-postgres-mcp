"""Recursive pglast AST walk → flags and category set."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pglast import ast

from lime_ref_postgres_mcp.infrastructure.sql._node_maps import (
    TXN_NODES,
    NodeCategory,
    classify_node_name,
)


@dataclass(frozen=True, slots=True)
class WalkResult:
    statement_count: int
    top_level_kind: str
    categories: frozenset[NodeCategory]
    has_modifying_cte: bool
    has_txn_control: bool
    is_explain_analyze: bool
    has_for_update: bool
    has_select_into: bool


def _apply_select_flags(node: ast.Node, flags: dict[str, bool]) -> None:
    if getattr(node, "lockingClause", None):
        flags["has_for_update"] = True
    if getattr(node, "intoClause", None):
        flags["has_select_into"] = True


def _apply_explain_flags(node: ast.Node, flags: dict[str, bool]) -> None:
    options = getattr(node, "options", None) or ()
    if any(getattr(opt, "defname", None) == "analyze" for opt in options):
        flags["is_explain_analyze"] = True


def _walk_subtree(node: ast.Node, categories: set[NodeCategory], flags: dict[str, bool]) -> None:
    name = type(node).__name__
    if name in TXN_NODES:
        flags["has_txn_control"] = True
    cat = classify_node_name(name)
    if cat is not None:
        categories.add(cat)
    if name == "SelectStmt":
        _apply_select_flags(node, flags)
    elif name == "ExplainStmt":
        _apply_explain_flags(node, flags)
    for attr in node:
        value = getattr(node, attr, None)
        if value is None:
            continue
        _walk_value(value, categories, flags)


def _walk_value(value: Any, categories: set[NodeCategory], flags: dict[str, bool]) -> None:
    if isinstance(value, ast.Node):
        _walk_subtree(value, categories, flags)
    elif isinstance(value, tuple):
        for item in value:
            _walk_value(item, categories, flags)


def _has_modifying_cte(root: ast.Node) -> bool:
    if type(root).__name__ != "SelectStmt":
        return False
    with_clause = getattr(root, "withClause", None)
    if with_clause is None:
        return False
    ctes = getattr(with_clause, "ctes", ()) or ()
    for cte in ctes:
        query = getattr(cte, "ctequery", None)
        if query is None:
            continue
        cats: set[NodeCategory] = set()
        flags = {"has_txn_control": False, "has_for_update": False, "has_select_into": False}
        _walk_subtree(query, cats, flags)
        if "DML" in cats:
            return True
    return False


def walk_statements(raw_statements: tuple[Any, ...]) -> WalkResult:
    statement_count = len(raw_statements)
    if statement_count == 0:
        return WalkResult(
            statement_count=0,
            top_level_kind="Empty",
            categories=frozenset(),
            has_modifying_cte=False,
            has_txn_control=False,
            is_explain_analyze=False,
            has_for_update=False,
            has_select_into=False,
        )
    root = raw_statements[0].stmt
    top_level_kind = type(root).__name__
    categories: set[NodeCategory] = set()
    flags = {
        "has_txn_control": False,
        "has_for_update": False,
        "has_select_into": False,
        "is_explain_analyze": False,
    }
    for raw in raw_statements:
        _walk_subtree(raw.stmt, categories, flags)
    has_modifying_cte = _has_modifying_cte(root)
    if has_modifying_cte:
        categories.add("DML")
    if flags["has_select_into"]:
        categories.add("DDL")
    return WalkResult(
        statement_count=statement_count,
        top_level_kind=top_level_kind,
        categories=frozenset(categories),
        has_modifying_cte=has_modifying_cte,
        has_txn_control=flags["has_txn_control"],
        is_explain_analyze=flags["is_explain_analyze"],
        has_for_update=flags["has_for_update"],
        has_select_into=flags["has_select_into"],
    )


__all__ = ["WalkResult", "walk_statements"]
