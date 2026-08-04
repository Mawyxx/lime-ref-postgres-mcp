"""SqlAnalysis value object — analyzer output shape (no parser in domain)."""

from __future__ import annotations

from dataclasses import dataclass

from lime_ref_postgres_mcp.domain.sql.types import SqlStatementClass


@dataclass(frozen=True, slots=True)
class SqlAnalysis:
    """Flags describing one analyzed SQL string (fixtures in P1, pglast in P1b)."""

    statement_class: SqlStatementClass
    statement_count: int
    top_level_kind: str
    has_modifying_cte: bool
    has_txn_control: bool
    is_explain_analyze: bool


__all__ = ["SqlAnalysis"]
