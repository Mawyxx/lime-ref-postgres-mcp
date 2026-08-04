"""Adversarial SQL SSOT for P1b (TDD §5.5)."""

from __future__ import annotations

from dataclasses import dataclass

from lime_ref_postgres_mcp.domain.sql.types import SqlStatementClass


@dataclass(frozen=True, slots=True)
class AdversarialCase:
    id: str
    sql: str
    expect_err: bool = False
    expect_class: SqlStatementClass | None = None
    expect_top_level: str | None = None
    expect_modifying_cte: bool | None = None
    expect_explain_analyze: bool | None = None
    guard_readonly: bool = False
    guard_explain: bool = False
    guard_write: bool = False


ADVERSARIAL_CASES: tuple[AdversarialCase, ...] = (
    AdversarialCase(
        id="Adv-1",
        sql="WITH x AS (DELETE FROM t RETURNING *) SELECT * FROM x",
        expect_class=SqlStatementClass.DML,
        expect_top_level="SelectStmt",
        expect_modifying_cte=True,
    ),
    AdversarialCase(
        id="Adv-2",
        sql="COMMIT; DROP SCHEMA public CASCADE",
        expect_class=SqlStatementClass.UNKNOWN,
    ),
    AdversarialCase(
        id="Adv-3",
        sql="SELECT 1; SELECT 2",
        expect_class=SqlStatementClass.UNKNOWN,
    ),
    AdversarialCase(
        id="Adv-4",
        sql="SELECT * FROM t FOR UPDATE",
        expect_class=SqlStatementClass.UNKNOWN,
        expect_top_level="SelectStmt",
    ),
    AdversarialCase(
        id="Adv-5",
        sql="SELECT * INTO new_t FROM t",
        expect_class=SqlStatementClass.DDL,
        expect_top_level="SelectStmt",
    ),
    AdversarialCase(
        id="Adv-6",
        sql="EXPLAIN ANALYZE DELETE FROM t",
        expect_class=SqlStatementClass.DML,
        expect_top_level="ExplainStmt",
        expect_explain_analyze=True,
    ),
    AdversarialCase(
        id="Adv-7",
        sql="COPY (SELECT 1) TO PROGRAM 'x'",
        expect_class=SqlStatementClass.ADMIN,
        expect_top_level="CopyStmt",
    ),
    AdversarialCase(
        id="Adv-8",
        sql="WITH x AS (INSERT INTO logs VALUES (1) RETURNING *) SELECT * FROM x",
        expect_class=SqlStatementClass.DML,
        expect_top_level="SelectStmt",
        expect_modifying_cte=True,
    ),
    AdversarialCase(
        id="Adv-9",
        sql="INSERT INTO t VALUES (1)",
        expect_class=SqlStatementClass.DML,
        expect_top_level="InsertStmt",
        guard_write=True,
    ),
    AdversarialCase(
        id="Adv-10",
        sql="DROP TABLE t",
        expect_class=SqlStatementClass.DDL,
        expect_top_level="DropStmt",
    ),
    AdversarialCase(
        id="Adv-P",
        sql="SELEC 1",
        expect_err=True,
    ),
)

__all__ = ["ADVERSARIAL_CASES", "AdversarialCase"]
