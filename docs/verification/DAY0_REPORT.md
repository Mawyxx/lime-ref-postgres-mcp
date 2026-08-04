# LIME Ref Postgres MCP — Day 0 Ship Report

**Date:** 2026-07-31  
**Package:** `lime_ref_postgres_mcp` `0.1.0`  
**Path:** `Marketing/lime-postgres-mcp/` (this package only)  
**Tier:** PRIME (scaffold only)  
**Status:** Day 0 complete — see later phases in P1_REPORT / Day0.5

---

## Isolation invariant

This package is a **standalone** project tree. All code, tests, docs, checker, and reports for it live **under this folder**. No imports from / writes to `srcN/`, root `scripts/`, or `docsN/` (except optional human reading of Prime standard elsewhere).

---

## Scope delivered

Composition kernel for the LIME agent-identity door:

| Component | Location |
|-----------|----------|
| Result (`Ok`/`Err`) + helpers | `domain/common/result.py` |
| `DomainError` / `InvariantViolation` | `domain/common/errors.py` |
| Frozen `Settings` + `ConfigurationError` | `bootstrap/settings.py` |
| `Runtime` + `build_runtime` | `bootstrap/container.py` |
| `Clock` / `IdGenerator` Protocols | `application/ports/clock.py` |
| `SystemClock` / `Uuid4IdGenerator` | `infrastructure/clock/` |
| Layer markers | presentation/mcp, subscribers, commands/services/context |
| Import-law tests | `tests/architecture/test_import_graph.py` |

**Out of scope (correctly absent):** MCP SDK, asyncpg, pglast, JWKS verify, policy/SQL VO, InvokeAgentTool, EventBus/sinks, `RequestContext`, `prime_check` FULL (~50 steps).

---

## Settings field freeze (TDD §12)

`lime_expected_domain`, `lime_jwks_url`, `agents_policy_path`, `policy_reload_ttl_seconds`, `postgres_url`, `pg_statement_timeout`, `pg_lock_timeout`, `pg_idle_in_transaction_timeout`, `pg_max_result_bytes`, `enable_console_event_sink` — plus later `log_*` / `metrics_enabled` (P5.1). Historical Day0 listed `webhook_url`; **removed** in P5.1 (no WebhookSink shipped).

Required at process start: `LIME_EXPECTED_DOMAIN`, `LIME_JWKS_URL`, `POSTGRES_URL`.  
Config failure → `ConfigurationError` (bootstrap), **not** `DomainError`.

---

## Runtime shape (Day 0)

```text
Runtime(settings: Settings, clock: Clock, ids: IdGenerator)
```

Later phases append attrs in `build_runtime` only (verifier, policy, db, bus, invoke…).

---

## Import law (enforced)

- `domain` → stdlib/typing only; no `os`, no bootstrap/infra/presentation
- `application` → domain + ports; no bootstrap/infra/presentation
- Banned in domain/application: `mcp`, `asyncpg`, `httpx`, `pglast`, `srcN`, …

---

## Verification commands

```text
cd Marketing/lime-postgres-mcp
uv sync --all-extras
uv run ruff check src tests          # exit 0
uv run mypy src                      # exit 0
uv run pytest                        # 25 passed, coverage 100% line+branch
uv run python -m lime_ref_postgres_mcp
# → scaffold: composition OK (no transport)  exit 0
```

---

## Isolation

- Own `pyproject.toml` + `uv.lock` (not root `lime-srcn`)
- No imports from `srcN`
- Result shape inspired by Core Result algebra, **local copy only**

---

## Next mandatory

**Day 0.5 — done.** See [DAY0_5_REPORT.md](./DAY0_5_REPORT.md).  
**Next:** P1 done — [P1_REPORT.md](./P1_REPORT.md). Next mandatory: **P1b** pglast analyzer.
