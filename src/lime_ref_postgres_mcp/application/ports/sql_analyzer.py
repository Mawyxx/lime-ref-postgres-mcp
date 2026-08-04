"""SqlAnalyzer port — AST parse/classify (CPU-bound, sync)."""

from __future__ import annotations

from typing import Protocol

from lime_ref_postgres_mcp.domain.common.errors import SqlParseFault
from lime_ref_postgres_mcp.domain.common.result import Result
from lime_ref_postgres_mcp.domain.sql.analysis import SqlAnalysis


class SqlAnalyzer(Protocol):
    """Parse SQL text into domain SqlAnalysis (implementation uses pglast in infra)."""

    def analyze(self, sql: str) -> Result[SqlAnalysis, SqlParseFault]: ...


__all__ = ["SqlAnalyzer"]
