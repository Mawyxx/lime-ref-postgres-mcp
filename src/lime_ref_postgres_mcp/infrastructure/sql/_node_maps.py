"""pglast node class names → SQL category buckets (data-only)."""

from __future__ import annotations

from typing import Final, Literal

NodeCategory = Literal["READ", "DML", "DDL", "ADMIN"]

READ_NODES: Final[frozenset[str]] = frozenset({"SelectStmt", "ValuesStmt"})
DML_NODES: Final[frozenset[str]] = frozenset(
    {"InsertStmt", "UpdateStmt", "DeleteStmt", "MergeStmt"}
)
DDL_NODES: Final[frozenset[str]] = frozenset(
    {
        "CreateStmt",
        "CreateTableAsStmt",
        "AlterTableStmt",
        "AlterDomainStmt",
        "AlterEnumStmt",
        "AlterObjectSchemaStmt",
        "DropStmt",
        "TruncateStmt",
        "RenameStmt",
        "IndexStmt",
        "CreateSchemaStmt",
        "CreateSeqStmt",
    }
)
ADMIN_NODES: Final[frozenset[str]] = frozenset(
    {
        "CopyStmt",
        "VacuumStmt",
        "ReindexStmt",
        "GrantStmt",
        "RevokeStmt",
        "ClusterStmt",
        "CommentStmt",
        "DiscardStmt",
        "CheckPointStmt",
    }
)
TXN_NODES: Final[frozenset[str]] = frozenset({"TransactionStmt"})


def classify_node_name(name: str) -> NodeCategory | None:
    if name in ADMIN_NODES:
        return "ADMIN"
    if name in DDL_NODES:
        return "DDL"
    if name in DML_NODES:
        return "DML"
    if name in READ_NODES:
        return "READ"
    return None


__all__ = [
    "ADMIN_NODES",
    "DDL_NODES",
    "DML_NODES",
    "NodeCategory",
    "READ_NODES",
    "TXN_NODES",
    "classify_node_name",
]
