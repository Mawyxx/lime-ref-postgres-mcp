"""Pure SQL guard: SqlAnalysis + tool + permissions → SqlGuardDecision."""

from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass

from lime_ref_postgres_mcp.domain.access.capability import ToolCapability
from lime_ref_postgres_mcp.domain.access.policy import (
    REASON_CAPABILITY_DENIED,
    REASON_STATEMENT_CLASS_DENIED,
)
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import RAW_SQL_TOOLS, ToolName
from lime_ref_postgres_mcp.domain.common.errors import StatementClassDenied
from lime_ref_postgres_mcp.domain.sql.analysis import SqlAnalysis
from lime_ref_postgres_mcp.domain.sql.types import (
    STATEMENT_CLASS_CAPABILITY,
    WRITE_TOP_LEVEL_KINDS,
    SqlStatementClass,
)


@dataclass(frozen=True, slots=True)
class SqlGuardDecision:
    """Pure allow/deny for raw-SQL tools."""

    statement_class: SqlStatementClass
    allowed: bool
    required_capability: ToolCapability | None
    reason_code: str | None

    def to_denied_error(self) -> StatementClassDenied | None:
        if self.allowed:
            return None
        return StatementClassDenied(
            invariant_id="sql.statement_class_denied",
            message="SQL statement class not allowed for tool",
            context={
                "statement_class": self.statement_class.value,
                "required_capability": (
                    self.required_capability.value if self.required_capability else None
                ),
                "reason_code": self.reason_code or REASON_STATEMENT_CLASS_DENIED,
            },
        )


def _deny(
    analysis: SqlAnalysis,
    *,
    required: ToolCapability | None,
    reason_code: str,
) -> SqlGuardDecision:
    return SqlGuardDecision(
        statement_class=analysis.statement_class,
        allowed=False,
        required_capability=required,
        reason_code=reason_code,
    )


def _allow(analysis: SqlAnalysis, required: ToolCapability | None) -> SqlGuardDecision:
    return SqlGuardDecision(
        statement_class=analysis.statement_class,
        allowed=True,
        required_capability=required,
        reason_code=None,
    )


def _base_structural_ok(analysis: SqlAnalysis) -> bool:
    return (
        analysis.statement_count == 1
        and not analysis.has_txn_control
        and analysis.statement_class != SqlStatementClass.UNKNOWN
    )


def _readonly_shape_ok(analysis: SqlAnalysis) -> bool:
    return (
        _base_structural_ok(analysis)
        and analysis.statement_class == SqlStatementClass.READ
        and not analysis.has_modifying_cte
    )


def guard(
    tool: ToolName,
    analysis: SqlAnalysis,
    permissions: Set[ToolCapability],
) -> SqlGuardDecision:
    """Decide whether raw SQL is allowed for tool + permissions (fail-closed)."""
    class_cap = STATEMENT_CLASS_CAPABILITY[analysis.statement_class]

    if tool not in RAW_SQL_TOOLS:
        return _deny(
            analysis,
            required=class_cap,
            reason_code=REASON_STATEMENT_CLASS_DENIED,
        )

    if not _base_structural_ok(analysis):
        return _deny(
            analysis,
            required=class_cap,
            reason_code=REASON_STATEMENT_CLASS_DENIED,
        )

    if tool in (ToolName.EXECUTE_READONLY_QUERY, ToolName.EXPLAIN_QUERY_PLAN):
        # EXPLAIN ANALYZE + mutate → non-READ class → denied by readonly shape.
        if not _readonly_shape_ok(analysis):
            return _deny(
                analysis,
                required=ToolCapability.READ_DATA,
                reason_code=REASON_STATEMENT_CLASS_DENIED,
            )
        if ToolCapability.READ_DATA not in permissions:
            return _deny(
                analysis,
                required=ToolCapability.READ_DATA,
                reason_code=REASON_CAPABILITY_DENIED,
            )
        return _allow(analysis, ToolCapability.READ_DATA)

    # execute_write_query
    if analysis.top_level_kind not in WRITE_TOP_LEVEL_KINDS:
        return _deny(
            analysis,
            required=ToolCapability.WRITE_DATA,
            reason_code=REASON_STATEMENT_CLASS_DENIED,
        )
    if analysis.statement_class != SqlStatementClass.DML:
        return _deny(
            analysis,
            required=class_cap,
            reason_code=REASON_STATEMENT_CLASS_DENIED,
        )
    if ToolCapability.WRITE_DATA not in permissions:
        return _deny(
            analysis,
            required=ToolCapability.WRITE_DATA,
            reason_code=REASON_CAPABILITY_DENIED,
        )
    return _allow(analysis, ToolCapability.WRITE_DATA)


__all__ = ["SqlGuardDecision", "guard"]
