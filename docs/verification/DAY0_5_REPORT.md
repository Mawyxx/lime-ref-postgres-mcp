# LIME Ref Postgres MCP — Day 0.5 Ship Report

**Date:** 2026-07-31  
**Package:** `lime_ref_postgres_mcp` `0.1.0`  
**Path:** `Marketing/lime-postgres-mcp/` (package-only)  
**Tier:** PRIME · `adoption_mode: greenfield`  
**Status:** Day 0.5 complete — P1 done (see [P1_REPORT.md](./P1_REPORT.md)); P1b next

---

## What landed

Package-local AGENT-5 checker:

| Artifact | Path |
|----------|------|
| Checker | `scripts/prime_check/` |
| Config | `scripts/prime_check.config.yaml` |
| Skip registry | `docs/adr/ADR-002-prime-check-na-skips.md` |
| Nested workflow | `.github/workflows/prime_check.yml` (extract-ready) |

**Isolation:** no writes to `srcN/`, root `scripts/`, `docsN/`, or root `.github/`.

---

## Verification

```text
cd Marketing/lime-postgres-mcp
uv sync --all-extras
uv run python -m scripts.prime_check --list
uv run python -m scripts.prime_check
# PASS=41 FAIL=0 SKIPPED=26
# prime_check: exit 0
# coverage_line/branch: 100.00%
```

Local command is **SSOT** inside the monorepo (nested `.github` may not be discovered by parent Actions).

---

## LIVE vs SKIPPED

- **LIVE:** preflight, static (ruff/mypy/format/vulture/size/complexity), 7 AST gates + supporting architecture, security (no-secrets/bandit/pip-audit/…), pytest + err/test matrix, coverage 100%, prod-config, evidence-block
- **SKIPPED(ADR-002):** gitleaks-history, zta/route, docker/health/tls, SQL/migrations, API/contract/integration, idempotency/FSM, ssrf/fuzz/sbom, mutation/frontend/CERT — see ADR-002 for `flip_phase`

---

## Evidence (sealed)

```text
PRIME-VERIFY-EVIDENCE
task: day0.5-prime-check-bootstrap
tier: PRIME
adoption_mode: greenfield
isolation: package-only
prime_check: exit 0
steps_live: 41
steps_skipped_adr: 26 (ADR-002)
coverage_line: 100.00%
coverage_branch: 100.00%
ci_workflow: .github/workflows/prime_check.yml
next_mandatory_task: P1 domain
```

---

## Next

**P1** complete — see [P1_REPORT.md](./P1_REPORT.md).  
**P1b** — `PglastSqlAnalyzer` + adversarial suite (no DB).
