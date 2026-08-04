"""SQL statement class and class→capability map."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Final

from lime_ref_postgres_mcp.domain.access.capability import ToolCapability


class SqlStatementClass(StrEnum):
    """AST-derived statement class (produced by analyzer in P1b)."""

    READ = "READ"
    DML = "DML"
    DDL = "DDL"
    ADMIN = "ADMIN"
    UNKNOWN = "UNKNOWN"


STATEMENT_CLASS_CAPABILITY: Final[Mapping[SqlStatementClass, ToolCapability | None]] = {
    SqlStatementClass.READ: ToolCapability.READ_DATA,
    SqlStatementClass.DML: ToolCapability.WRITE_DATA,
    SqlStatementClass.DDL: ToolCapability.DDL,
    SqlStatementClass.ADMIN: ToolCapability.ADMIN,
    SqlStatementClass.UNKNOWN: None,
}

WRITE_TOP_LEVEL_KINDS: Final[frozenset[str]] = frozenset({"InsertStmt", "UpdateStmt", "DeleteStmt"})


__all__ = [
    "STATEMENT_CLASS_CAPABILITY",
    "WRITE_TOP_LEVEL_KINDS",
    "SqlStatementClass",
]
