# LIME Ref Postgres MCP — P3 Ship Report

**Date:** 2026-08-01  
**Package:** `lime_ref_postgres_mcp` `0.1.0`  
**Path:** `Marketing/lime-postgres-mcp/` (package-only)  
**Tier:** PRIME · `adoption_mode: greenfield`  
**Status:** P3 complete — see [P4_REPORT.md](./P4_REPORT.md) for next phase ship  
**Report standard:** [README.md](./README.md)

---

## What landed

Real identity + policy infrastructure adapters. P2 invoke pipeline **unchanged**. DB still scaffold until P4.

| Area | Paths | Role |
|------|-------|------|
| Verifier | `infrastructure/identity/lime_passport_verifier.py` | Wraps `lime_mcp_server.TokenVerifier` -> `PassportClaims` / Result |
| Domain pin | `infrastructure/identity/domain_normalize.py` | ADR 0095 hostname normalize for Settings |
| JWKS URL | `infrastructure/identity/lime_base_url.py` | Derive SDK `base_url` from `LIME_JWKS_URL` |
| Policy store | `infrastructure/policy/json_agent_policy_store.py` | Disk JSON + TTL/mtime cache + soft-keep |
| Settings | `bootstrap/settings.py` | `LIME_EXPECTED_AUD`, JWKS TTL, JWT leeway |
| Factories | `bootstrap/container.py` | `create_*`, `build_scaffold_runtime()` |
| Entry | `__main__.py` | Composition via `build_scaffold_runtime()` (DB scaffold) |

**Locked contracts preserved:**

- Pre-auth `Err` -> **no emit** (ZTA Z1–Z10 still on fakes)
- `PolicyDocument.from_mapping` SSOT for JSON schema
- `build_runtime` still requires explicit `verifier` / `policy_store` / `database`

---

## Implementation walkthrough

### `LimePassportVerifier` (~128 LOC)

1. `_strip_bearer` — blank / bare `Bearer` -> `PassportMissing`; strip `Bearer ` prefix.
2. `await token_verifier.verify_async(token)` (SDK or injected fake).
3. Invalid / missing claims -> `PassportInvalid` with `context.reason_code` mapped from SDK error text.
4. Valid -> `AgentId.parse(sub)` -> `PassportClaims` (never stores raw JWT).
5. `warmup()` / `close()` delegate to owned SDK instance.

**Crypto / JWKS / aud / domain pin / forbidden AIT claims:** owned by `lime-mcp-server-sdk` `TokenVerifier`. Adapter is a thin Result mapper.

### `JsonAgentPolicyStore` (~155 LOC)

1. Under `asyncio.Lock`: if snapshot fresh within TTL -> return cached `PolicyDocument`.
2. Else `stat` mtime; unchanged -> bump `checked_at`.
3. Else read bytes -> `json.loads` -> `PolicyDocument.from_mapping`.
4. Success -> atomic `_Snapshot` replace.
5. Failure with prior good snapshot -> **soft-keep** (return old `Ok`, bump `checked_at`).
6. First-load failure -> `PolicyStoreFault` (`file_not_found` / `parse_error` / `schema_invalid` / `io_error`).

### Bootstrap

- `create_passport_verifier(settings)` / `create_policy_store(settings, clock)`
- `build_scaffold_runtime()` wires Lime + Json + `ScaffoldUnavailableDatabase` + shared `SystemClock`
- `__main__` only calls `build_scaffold_runtime()` (di-graph: no infra ctors outside `bootstrap/`)

### Dependency note

`lime-mcp-server-sdk` pins `cryptography<45`. Package uses `[tool.uv] override-dependencies = ["cryptography>=48.0.1"]` so `pip-audit` stays green (Prime A19) while keeping the SDK verify contract.

---

## Naming & readability

| Name | Why |
|------|-----|
| `LimePassportVerifier` | LIME MCP passport, not site-login AIT |
| `JsonAgentPolicyStore` | File-backed `AgentPolicyStore` |
| `normalize_mcp_domain` | Explicit ADR 0095 semantics |
| `build_scaffold_runtime` | Prod identity/policy + scaffold DB boundary |
| `reason_code` in error context | Observability without leaking tokens |

---

## Function size & complexity

| File | LOC | Notes |
|------|-----|-------|
| `json_agent_policy_store.py` | 155 | Lock + reload helpers; cyclomatic ok |
| `lime_passport_verifier.py` | 128 | Reason table + strip helper split for A11 |
| `domain_normalize.py` | 33 | Split `_from_url` / `_from_plain` / `_reject_ip` |
| `lime_base_url.py` | 23 | Pure URL helper |
| `settings.py` | ~120 | Added aud / JWKS TTL / leeway |

---

## Deliberate simplicity

- Did **not** reimplement JWKS crypto — wrap SDK.
- Did **not** change Establish / Invoke / Authorize / Emit / `guard.py`.
- Did **not** put allowlist rules in the JSON adapter.
- Did **not** arm `ssrf-gate` (still P5) or `pytest-integration` (P4).
- Did **not** hit live lime.pics in tests (injected `TokenVerifier` fakes).

---

## Maintainability (1-year view)

| Next | Touch | Stable |
|------|-------|--------|
| **P4** | `AsyncpgDatabaseGateway` + replace scaffold DB in `build_scaffold_runtime` | Identity/policy adapters, P2 services |
| **P5** | MCP handlers + optional `warmup()`; maybe arm `ssrf-gate` | Ports unchanged |

**Risk:** SDK cryptography pin vs override — revisit when `lime-mcp-server-sdk` bumps its pin. Soft-keep window equals policy TTL (ops must wait ≤ TTL after corrupt file write).

---

## Quality rubric

| Dimension | Score | Evidence |
|-----------|-------|----------|
| Readability | Strong | Thin adapter + one store algorithm |
| Naming | Strong | Phase verbs / MCP vs AIT clear |
| Small functions | Strong | Cyclomatic splits for reason codes + domain normalize |
| No over-engineering | Strong | No plugin registry; factories only |
| Year-ahead | OK | P4 is DB swap; SDK override documented |

---

## Threat notes (A16)

| Threat | Mitigation |
|--------|------------|
| Stolen passport JWT | Short-lived JWT + domain pin + allowlist (Establish) |
| JWKS unreachable | Fail closed -> `PassportInvalid` / `jwks_unavailable` |
| Policy file tamper / bad write | Soft-keep last good; first load Fault; TTL bounds stale allowlist |

---

## Test matrix

| ID | File |
|----|------|
| P-1..P-8 + concurrency | `tests/unit/infrastructure/policy/test_json_agent_policy_store.py` |
| V-1..V-10 + base_url | `tests/unit/infrastructure/identity/test_lime_passport_verifier.py` |
| Domain normalize | `tests/unit/infrastructure/identity/test_domain_normalize.py` |
| Settings / main / factories | `tests/unit/bootstrap/*`, `tests/unit/test_main.py` |
| ZTA Z1–Z10 | unchanged fakes (`tests/contract/test_zta_matrix.py`) |

---

## Out of scope (deferred)

| Item | Phase |
|------|-------|
| `AsyncpgDatabaseGateway` + Testcontainers | **P4** |
| MCP handlers, ConsoleSink, `ssrf-gate` LIVE | **P5** |

---

## Verification

```text
cd Marketing/lime-postgres-mcp
uv sync --all-extras
uv run ruff check src tests
uv run mypy src
uv run pytest
uv run python -m scripts.prime_check
# pytest: 267 passed
# PASS=43 FAIL=0 SKIPPED=24
# prime_check: exit 0
# coverage_line/branch: 100.00%
```

---

## Evidence (sealed)

```text
PRIME-VERIFY-EVIDENCE
task: p3-json-policy-lime-passport-verifier
tier: PRIME
adoption_mode: greenfield
isolation: package-only (Marketing/lime-postgres-mcp)
scope: LimePassportVerifier + JsonAgentPolicyStore + Settings aud + __main__ wiring (DB still scaffold)
injection-fuzz: LIVE
zta-matrix-gate: LIVE
ssrf-gate: SKIPPED (ADR-002 flip_phase P5)
prime_check: exit 0
steps_live: 43
steps_skipped_adr: 24 (ADR-002)
coverage_line: 100.00%
coverage_branch: 100.00%
uncovered: NONE
next_mandatory_task: P4 AsyncpgDatabaseGateway + Testcontainers
last_cmd: uv run python -m scripts.prime_check
```

---

## Next

**P4 done** — see [P4_REPORT.md](./P4_REPORT.md). Next mandatory: **P5** MCP presentation + ConsoleSink.
