# LIME Ref Postgres MCP — P1b Ship Report

**Date:** 2026-08-01  
**Package:** `lime_ref_postgres_mcp` `0.1.0`  
**Path:** `Marketing/lime-postgres-mcp/` (package-only)  
**Tier:** PRIME · `adoption_mode: greenfield`  
**Status:** P1b complete — P2 unlocked  
**Report standard:** [README.md](./README.md) — older reports gain maintainability sections when updated

---

## What landed

Defense layer #2: real PostgreSQL AST → existing P1 `SqlAnalysis` → unchanged `guard()`.

| Area | Paths |
|------|--------|
| Port | `application/ports/sql_analyzer.py` — sync `SqlAnalyzer.analyze(sql) -> Result[SqlAnalysis, SqlParseFault]` |
| Node maps | `infrastructure/sql/_node_maps.py` — READ/DML/DDL/ADMIN/TXN frozensets |
| AST walk | `infrastructure/sql/ast_walk.py` — recursive walk → flags + categories |
| Classifier | `infrastructure/sql/ast_classify.py` — priority ADMIN > DDL > DML > READ |
| Adapter | `infrastructure/sql/pglast_sql_analyzer.py` — parse → walk → classify → `SqlAnalysis` |
| Adversarial SSOT | `tests/unit/infrastructure/sql/adversarial_cases.py` — Adv-1..10 + Adv-P |

**Locked behavior:**

- `pglast` import only in `infrastructure/sql/*` (domain/application pglast-free)
- Empty/whitespace or syntax error → `Err(SqlParseFault)`; context has `parse_error` only (no raw SQL)
- Multi-stmt, txn control, FOR UPDATE → `Ok(..., statement_class=UNKNOWN)` (fail-closed)
- SELECT INTO → `DDL`; modifying CTE → `has_modifying_cte=True`, class ≥ DML
- EXPLAIN ANALYZE → `is_explain_analyze=True`; class from inner stmt
- **`domain/sql/guard.py` unchanged** — analyzer must emit P1-compatible `SqlAnalysis`
- **Zero** bootstrap wiring (`container.py` untouched until P2)

---

## Implementation & maintainability (summary)

P1b is an **adapter layer** between `pglast` and the frozen P1 domain (`SqlAnalysis`, `guard()`). Logic is split by concern so each file stays small and testable.

| Module | LOC (approx) | Responsibility |
|--------|--------------|----------------|
| `pglast_sql_analyzer.py` | ~60 | Parse → walk → classify → `Result[SqlAnalysis, SqlParseFault]` |
| `ast_walk.py` | ~80 | Recursive AST visit; sets flags (`has_modifying_cte`, `is_explain_analyze`, …) |
| `ast_classify.py` | ~40 | Priority: ADMIN > DDL > DML > READ → `StatementClass` |
| `_node_maps.py` | ~50 | Frozensets of pglast node tags — data, not logic |

**Naming:** `PglastSqlAnalyzer` (infra), `SqlAnalyzer` (port), `SqlParseFault` (domain) — dependency direction is obvious from names. No `parse_sql()` god function; walk and classify are separately unit-tested.

**Why not one file:** cyclomatic gate + adversarial matrix (Adv-1..10) require isolated tests on walk/classify without spinning up full parse for every edge case.

**Year-ahead:** P2+ only injects `SqlAnalyzer` via port; swapping analyzer or adding dialect quirks touches `infrastructure/sql/*` only. `guard.py` never changes.

| Dimension | Score | Note |
|-----------|-------|------|
| Readability | Strong | Pipeline parse → walk → classify is linear in analyzer |
| Naming | Strong | Port vs adapter vs fault types distinct |
| Small functions | Strong | Walk/classify split |
| No over-engineering | Strong | No plugin AST framework |
| Year-ahead | Strong | Domain remains pglast-free |

Full rubric: [README.md](./README.md).

---

## Adversarial matrix (TDD §5.5)

| ID | Expected class | RO | EXPLAIN | WRITE |
|----|----------------|----|---------|-------|
| Adv-1 CTE DELETE + SELECT | DML | deny | deny | deny |
| Adv-2 COMMIT; DROP SCHEMA | UNKNOWN | deny | deny | deny |
| Adv-3 two SELECTs | UNKNOWN | deny | deny | deny |
| Adv-4 FOR UPDATE | UNKNOWN | deny | deny | deny |
| Adv-5 SELECT INTO | DDL | deny | deny | deny |
| Adv-6 EXPLAIN ANALYZE DELETE | DML | deny | deny | deny |
| Adv-7 COPY TO PROGRAM | ADMIN | deny | deny | deny |
| Adv-8 CTE INSERT + SELECT | DML | deny | deny | deny |
| Adv-9 plain INSERT | DML | deny | deny | **allow** |
| Adv-10 DROP TABLE | DDL | deny | deny | deny |
| Adv-P invalid syntax | Err | — | — | — |

---

## Test matrix

| ID | Covered in |
|----|------------|
| Ana-1..5 | `tests/unit/infrastructure/sql/test_pglast_sql_analyzer.py` |
| Adv-1..10, Adv-P | `tests/unit/infrastructure/sql/test_adversarial_sql.py` |
| Pipe-1..10 | `tests/unit/infrastructure/sql/test_analyze_then_guard.py` |
| AST edge cases | `tests/unit/infrastructure/sql/test_ast_internals.py` |
| Port smoke | `tests/unit/application/ports/test_sql_analyzer_port.py` |

---

## Out of scope (deferred)

| Item | Phase |
|------|--------|
| `InvokeAgentToolService` / `RequestContext` / EventBus | **P2** |
| Bootstrap DI wiring for `PglastSqlAnalyzer` | **P2** |
| JsonPolicyStore disk load / JWKS | **P3** |
| asyncpg / MCP presentation | **P4 / P5** |

---

## Verification

```text
cd Marketing/lime-postgres-mcp
uv sync --all-extras
uv run ruff check src tests
uv run mypy src
uv run pytest
uv run python -m scripts.prime_check
# PASS=42 FAIL=0 SKIPPED=25
# prime_check: exit 0
# coverage_line/branch: 100.00%
# injection-fuzz: LIVE
```

---

## Evidence (sealed)

```text
PRIME-VERIFY-EVIDENCE
task: p1b-pglast-sql-analyzer-adversarial
tier: PRIME
adoption_mode: greenfield
isolation: package-only (Marketing/lime-postgres-mcp)
scope: SqlAnalyzer port + PglastSqlAnalyzer + adversarial + analyze->guard (no MCP, no DB, no Invoke*)
injection-fuzz: LIVE
prime_check: exit 0
steps_live: 42
steps_skipped_adr: 25 (ADR-002)
coverage_line: 100.00%
coverage_branch: 100.00%
uncovered: NONE
next_mandatory_task: P2 InvokeAgentToolService + Fake ports + ZTA partial (done — see P2_REPORT.md)
last_cmd: uv run python -m scripts.prime_check
```

---

## Next

**P3** — `JsonAgentPolicyStore` + `LimePassportVerifier`. P2 invoke layer: [P2_REPORT.md](./P2_REPORT.md).
