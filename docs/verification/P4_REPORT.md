# LIME Ref Postgres MCP — P4 Ship Report

**Date:** 2026-08-01  
**Package:** `lime_ref_postgres_mcp` `0.1.0`  
**Path:** `Marketing/lime-postgres-mcp/` (package-only)  
**Tier:** PRIME · `adoption_mode: greenfield`  
**Status:** P4 complete — P5 unlocked  
**Report standard:** [README.md](./README.md)

---

## What landed

Real Postgres adapter for `DatabaseGateway`. P2 invoke pipeline and P3 identity/policy **unchanged**. ZTA Z1–Z10 stay on fakes.

| Area | Paths | Role |
|------|-------|------|
| Gateway | `infrastructure/postgres/asyncpg_database_gateway.py` | Port impl: txn envelope, timeouts, limits |
| Pool | `infrastructure/postgres/pool.py` | `create_pool(settings)` |
| Limits | `infrastructure/postgres/result_limits.py` | Row/byte clamp + JSON normalize |
| Idents | `infrastructure/postgres/identifiers.py` | Allowlist + quote for `select_rows` |
| Faults | `infrastructure/postgres/faults.py` | asyncpg/OS → masked `DatabaseFault` |
| Settings | `bootstrap/settings.py` | `PG_POOL_MIN_SIZE` / `PG_POOL_MAX_SIZE` |
| Factory | `bootstrap/container.py` | `create_database` + scaffold swap |
| Entry | `__main__.py` | Lazy DB composition smoke (no TCP) |
| Integration | `tests/integration/` | Testcontainers Postgres G-1..G-11 |
| Gate | `pytest-integration` | LIVE (ADR-002 flip) |

**Locked contracts preserved:**

- `run_execution_plan` single dispatch site — not edited
- Port method signatures unchanged
- Pre-auth / ZTA on fakes
- Event `reason_code=database_fault` mapping unchanged in Invoke

---

## Implementation walkthrough

### Session envelope (every call)

1. Lazy `await _acquire_pool()` (lock-protected once).
2. `async with pool.acquire()` → `conn.transaction(readonly=…)`.
3. Bound `set_config` for `statement_timeout`, `lock_timeout`, `idle_in_transaction_session_timeout`.
4. Read path: `set_config('transaction_read_only', 'on', true)`.
5. Exactly one asyncpg statement (`fetch` / `cursor.fetch` / `execute`).
6. Row limit (`max_rows + 1`) and UTF-8 JSON byte limit — fail closed.
7. Context manager commits; exceptions → `map_asyncpg_fault` → `Err(DatabaseFault)`.

### `AsyncpgDatabaseGateway` (~262 LOC)

- **Ctor + `from_settings`:** explicit pool for tests; lazy settings-backed open for composition.
- **Catalog tools:** fixed SQL + `$n` bound params (`list_*`, `get_table_schema`, `database_stats`).
- **`select_rows`:** allowlisted quoted identifiers + bound `LIMIT`/`OFFSET`.
- **`execute_readonly` / `explain`:** read-only txn; explain prefixes `EXPLAIN (FORMAT TEXT)` when needed.
- **`execute_write`:** read-write txn; `{"ok": true}` + parsed `affected_rows`.
- **`open` / `close`:** process lifecycle (not on Protocol).

### Bootstrap

`create_database(settings) -> AsyncpgDatabaseGateway.from_settings(settings)`.  
`build_scaffold_runtime` wires it instead of `ScaffoldUnavailableDatabase` (scaffold class kept for unit injection).

`__main__` remains sync smoke: **no pool open** until a DB method runs.

---

## Naming & readability

| Name | Why |
|------|-----|
| `AsyncpgDatabaseGateway` | Driver + port role in one noun |
| `create_pool` / `create_database` | Mirror P3 `create_*` factories |
| `quote_ident` / `map_asyncpg_fault` | Pure helpers, testable without pool |
| `enforce_row_limit` / `enforce_byte_limit` | Fail-closed vocabulary matches fault ids |

Reader sees port methods first, then private `_with_txn` / `_apply_guards` envelope.

---

## Function size & complexity

| File | LOC | Notes |
|------|-----|-------|
| `asyncpg_database_gateway.py` | 262 | Under 300; helpers split out |
| `result_limits.py` | 113 | `normalize_cell` split via `_normalize_scalar` (cyclo ≤10) |
| `faults.py` / `identifiers.py` / `pool.py` | small | Single responsibility |

No god `_execute(flags=…)` — separate `_read_rows` / `_read_names` / write body.

---

## Deliberate simplicity

- Did **not** make `build_runtime` async.
- Did **not** add second `PG_MAX_ROWS` Settings ceiling (policy clamp remains SSOT).
- Did **not** re-parse SQL in the gateway (AST stays in Authorize).
- Did **not** move ZTA onto live Postgres.
- Did **not** truncate oversized results — fail closed.
- Did **not** ship MCP handlers / sinks (P5).

---

## Maintainability (1-year view)

| Next | Touch | Stable |
|------|-------|--------|
| **P5** | MCP handlers, ConsoleSink, maybe pool warmup on lifespan | Gateway port + envelope |
| Pool tuning | Settings only | Gateway body |
| Extra catalog columns | `_SQL_*` constants | Port signatures |

**Risk:** Testcontainers needs Docker in CI/local for `pytest-integration`. Unit suite stays Docker-free via `-m "not integration"`.

---

## Quality rubric

| Dimension | Score | Evidence |
|-----------|-------|----------|
| Readability | Strong | Envelope helpers + Fake-matching payloads |
| Naming | Strong | Fault invariant_ids stable and agent-safe |
| Small functions | Strong | A11 file/cyclo gates green |
| No over-engineering | Strong | Lazy pool; no async composition rewrite |
| Year-ahead | Strong | P5 only adds presentation on top |

---

## Threat notes (A16)

| Threat | Mitigation |
|--------|------------|
| SQL injection via identifiers | Allowlist + quote; values bound |
| DoS `pg_sleep` / heavy CTE | `SET LOCAL` timeouts + max_rows + max_bytes |
| Multi-statement escape | asyncpg extended protocol + AST (Z9) |
| Error leakage | Masked `DatabaseFault` messages |
| Read path write | `BEGIN READ ONLY` + `transaction_read_only=on` |

---

## Test matrix

| ID | File |
|----|------|
| U-1..U-5 + branches | `tests/unit/infrastructure/postgres/test_asyncpg_database_gateway.py` |
| Pool factory | `tests/unit/infrastructure/postgres/test_pool.py` |
| G-1..G-11 + stats | `tests/integration/test_postgres_gateway.py` |
| Bootstrap / main | `tests/unit/bootstrap/*`, `tests/unit/test_main.py` |
| ZTA Z1–Z10 | unchanged fakes |

---

## Out of scope (deferred)

| Item | Phase |
|------|-------|
| MCP handlers, `extract_bearer`, ConsoleSink | **P5** |
| `ssrf-gate` LIVE | N/A-showcase (no outbound audit HTTP) |
| WebhookSink | out of scope (integrator) |

---

## Verification

```text
cd Marketing/lime-postgres-mcp
uv sync --all-extras
uv run ruff check src tests
uv run mypy src
uv run pytest
uv run pytest tests/integration -m integration --no-cov -o addopts=
uv run python -m scripts.prime_check
# unit: 300 passed (integration deselected), 100% cov
# integration: 12 passed (Docker/Testcontainers)
# PASS=44 FAIL=0 SKIPPED=23
# prime_check: exit 0
```

---

## Evidence (sealed)

```text
PRIME-VERIFY-EVIDENCE
task: p4-asyncpg-database-gateway
tier: PRIME
adoption_mode: greenfield
isolation: package-only (Marketing/lime-postgres-mcp)
scope: AsyncpgDatabaseGateway + lazy pool + Testcontainers + build_scaffold_runtime DB swap
injection-fuzz: LIVE
zta-matrix-gate: LIVE
pytest-integration: LIVE
ssrf-gate: SKIPPED (ADR-002 flip_phase P5)
prime_check: exit 0
steps_live: 44
steps_skipped_adr: 23 (ADR-002)
coverage_line: 100.00%
coverage_branch: 100.00%
uncovered: NONE
next_mandatory_task: P5 MCP presentation + ConsoleSink
last_cmd: uv run python -m scripts.prime_check
```

---

## Next

**P5 done** — see [P5_REPORT.md](./P5_REPORT.md). **P5.1** observability next. WebhookSink is out of scope for showcase maintainers.
