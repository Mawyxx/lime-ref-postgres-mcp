# LIME Ref Postgres MCP — P1 Ship Report

**Date:** 2026-08-01  
**Package:** `lime_ref_postgres_mcp` `0.1.0`  
**Path:** `Marketing/lime-postgres-mcp/` (package-only)  
**Tier:** PRIME · `adoption_mode: greenfield`  
**Status:** P1 complete — see [P1B_REPORT.md](./P1B_REPORT.md) for analyzer layer

---

## What landed

Pure domain identity-door kernel (no I/O, no pglast, no MCP, no DB):

| Area | Paths |
|------|--------|
| AgentId | `domain/agent/agent_id.py` |
| Capabilities / policy | `domain/access/{capability,policy,authorized_agent,capability_check}.py` |
| Tool catalog SSOT | `domain/catalog/tool_catalog.py` |
| SQL analysis + guard | `domain/sql/{types,analysis,guard}.py` |
| Audit VO shape | `domain/auditing/{event_outcome,agent_action_event}.py` |
| Named errors | `domain/common/errors.py` (extended) |

**Locked behavior:**

- `PolicyDocument.from_mapping` / `resolve` / `clamp_limit` + `DEFAULT_PERMISSIONS`
- `capability_check` → `CapabilityDecision` + `to_denied_error()`
- `guard` only for `RAW_SQL_TOOLS`; fail-closed otherwise
- `reason_code` SSOT: `capability_denied` \| `statement_class_denied`
- `EventOutcome` + `AgentActionEvent` construction-only (no EventBus)

---

## Test matrix

| ID | Covered in |
|----|------------|
| Pol-1…5 | `tests/unit/domain/access/test_policy.py` |
| Cap-1…3 | `tests/unit/domain/access/test_capability_check.py` |
| Cat-1 | `tests/unit/domain/catalog/test_tool_catalog.py` |
| Grd-1…7 | `tests/unit/domain/sql/test_guard.py` (+ builders) |
| Err-* | `tests/unit/domain/common/test_errors.py` |
| Immut-1 | policy / guard / event / AgentId frozen tests |

---

## Out of scope (deferred)

| Item | Phase |
|------|--------|
| `pglast` / `PglastSqlAnalyzer` / adversarial SQL strings | **P1b** — [P1B_REPORT.md](./P1B_REPORT.md) |
| `InvokeAgentToolService` / `RequestContext` / EventBus | **P2** |
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
# PASS=41 FAIL=0 SKIPPED=26
# prime_check: exit 0
# coverage_line/branch: 100.00%
```

---

## Evidence (sealed)

```text
PRIME-VERIFY-EVIDENCE
task: p1-domain-policy-capabilities-sql-guard
tier: PRIME
adoption_mode: greenfield
isolation: package-only (Marketing/lime-postgres-mcp)
scope: domain-only (no pglast, no MCP, no DB, no Invoke*)
pytest: exit 0
prime_check: exit 0
coverage_line: 100.00%
coverage_branch: 100.00%
uncovered: NONE
deliverables: AgentId,ToolCapability,PolicyDocument,tool_catalog,SqlAnalysis,SqlGuardDecision,CapabilityDecision,named DomainErrors,AgentActionEvent
next_mandatory_task: P1b PglastSqlAnalyzer + adversarial suite (done — see P1B_REPORT.md)
last_cmd: uv run python -m scripts.prime_check
```

---

## Next

**P2** — `InvokeAgentToolService` + Fake ports + ZTA partial. P1b analyzer: [P1B_REPORT.md](./P1B_REPORT.md).
