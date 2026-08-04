"""Pure classification: walk flags + categories → SqlStatementClass."""

from __future__ import annotations

from lime_ref_postgres_mcp.domain.sql.types import SqlStatementClass
from lime_ref_postgres_mcp.infrastructure.sql._node_maps import NodeCategory
from lime_ref_postgres_mcp.infrastructure.sql.ast_walk import WalkResult

_PRIORITY: tuple[NodeCategory, ...] = ("ADMIN", "DDL", "DML", "READ")


def resolve_statement_class(walk: WalkResult) -> SqlStatementClass:
    if walk.statement_count != 1:
        return SqlStatementClass.UNKNOWN
    if walk.has_txn_control:
        return SqlStatementClass.UNKNOWN
    if walk.has_for_update:
        return SqlStatementClass.UNKNOWN
    if not walk.categories:
        return SqlStatementClass.UNKNOWN
    for level in _PRIORITY:
        if level in walk.categories:
            return SqlStatementClass(level)
    return SqlStatementClass.UNKNOWN


__all__ = ["resolve_statement_class"]
