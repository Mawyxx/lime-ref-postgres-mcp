# LIME Ref Postgres MCP — P2 Ship Report

**Date:** 2026-08-01  
**Package:** `lime_ref_postgres_mcp` `0.1.0`  
**Path:** `Marketing/lime-postgres-mcp/` (package-only)  
**Tier:** PRIME · `adoption_mode: greenfield`  
**Status:** P2 complete — P3 unlocked  
**Report standard:** [README.md](./README.md) (implementation + maintainability sections required)

---

## What landed

End-to-end **invoke pipeline**: passport → policy → authorize → DB plan → emit audit event. Fake ports + ZTA contract matrix; `zta-matrix-gate` **LIVE**.

| Area | Paths | Role |
|------|-------|------|
| Ports | `application/ports/{identity,policy,database,events}.py` | `PassportVerifier`, `AgentPolicyStore`, `DatabaseGateway`, `EventBus` |
| Command | `application/commands/invoke_agent_tool.py` | `InvokeAgentToolCommand` — tool + args + optional bearer/request_id |
| Context | `application/context/{request_context,agent_reply,execution_plan,db_payload}.py` | Immutable DTOs between steps |
| Services | `establish_request_context.py`, `authorize_tool.py`, `run_execution_plan.py`, `emit_agent_action.py`, `invoke_agent_tool.py` | Pipeline steps + facade |
| Events | `infrastructure/events/in_process_event_bus.py` | Sequential in-process bus |
| Bootstrap | `bootstrap/container.py`, `bootstrap/scaffold.py` | `build_runtime()` + fail-closed rejectors for `__main__` |
| Fakes | `tests/fakes/*`, `tests/support/build_test_runtime.py` | Deterministic test wiring |
| Contract | `tests/contract/test_zta_matrix.py` | Z1–Z10 (real `PglastSqlAnalyzer` on SQL paths) |
| Gates | `scripts/security/zta_matrix_gate.py` | prime_check step **LIVE** |

**Locked return contract:**

| Stage | On failure | Emit? | Caller gets |
|-------|------------|-------|-------------|
| Pre-auth (`EstablishRequestContext`) | `PassportMissing`, `PassportInvalid`, `AgentNotAllowlisted`, `PolicyStoreFault` | **No** | `Err(PreAuthError)` |
| Post-auth (authorize / DB / success) | denied / error / ok | **Exactly one** | `Ok(AgentReply)` |

`EventOutcome` SSOT stays in `domain/auditing/event_outcome.py` — application builds it, never duplicates the type.

**Unchanged:** `domain/sql/guard.py` (P1 lock).

---

## Implementation walkthrough

### Pipeline (facade)

```
InvokeAgentToolCommand
  → EstablishRequestContextService.execute()     [async]
  → AuthorizeToolService.execute()               [sync]
  → run_execution_plan(db, plan)                 [async]
  → EmitAgentActionService.emit(ctx, status, outcome)  [async]
  → Result[AgentReply, PreAuthError]
```

Only `InvokeAgentToolService` knows the full sequence. Sub-services do not call each other.

### `EstablishRequestContextService` (~58 LOC)

**File:** `application/services/establish_request_context.py`

1. Resolve `request_id` from command or `IdGenerator`.
2. Reject empty/missing bearer → `Err(PassportMissing)` (no strip-only bypass).
3. `await verifier.verify(token)` — propagate verifier errors unchanged.
4. `await policy_store.current()` — propagate store faults.
5. `document.resolve(agent_id)` → `AuthorizedAgent.from_policy(...)`.
6. Build frozen `RequestContext` with `PolicySnapshot`, tool, args copy, `started_at`.

**Return contract:** `Result[RequestContext, PreAuthError]` where `PreAuthError` is a typed union alias at module top — callers know pre-auth failures without reading the body.

### `AuthorizeToolService` (~141 LOC)

**File:** `application/services/authorize_tool.py`

1. `capability_check(tool, permissions)` — domain pure function; map to `CapabilityDenied` if blocked.
2. If tool ∈ `RAW_SQL_TOOLS`: validate `sql` string → `analyzer.analyze()` → `guard(tool, analysis, permissions)`.
3. `_build_plan(ctx)` — tool-specific plan builders:
   - `_plan_list_tables`, `_plan_get_table_schema`, `_plan_select_rows` — arg validation via `_require_str` / `_input_invalid`
   - `_plan_raw_sql` — readonly / explain / write branches with `doc.clamp_limit()`
   - catalog tools without args → zero-field plans (`ListSchemasPlan`, `DatabaseStatsPlan`)
4. `assert_never(tool)` on exhaustive `ToolName` match — mypy + runtime exhaustiveness.

**Return contract:** `Result[ExecutionPlan, AuthzError]` — plan is ready for DB dispatch; no I/O here.

### `run_execution_plan` (~39 LOC)

**File:** `application/services/run_execution_plan.py`

Single **match site** for `DatabaseGateway`: one `isinstance` branch per plan type, then `assert_never(plan)`. P4 `AsyncpgDatabaseGateway` implements the port; this function never changes when SQL drivers swap.

### `EmitAgentActionService` (~50 LOC)

**File:** `application/services/emit_agent_action.py`

- Accepts `(ctx, status, outcome)` — **never** `AgentReply` (reply is HTTP/MCP concern; outcome is audit SSOT).
- `sanitize_args()` strips `_SECRET_KEYS` (authorization, bearer, password, …) before event payload.
- Computes `duration_ms` from `ctx.started_at` and `clock.now_utc()`.
- Builds `AgentActionEvent` → `await event_bus.emit()`.

### `InvokeAgentToolService` (~110 LOC)

**File:** `application/services/invoke_agent_tool.py`

1. `establish` → on `Err`, return immediately (**no emit**).
2. `authorize` → on `Err`, `_authz_to_reply_and_outcome()` maps each `AuthzError` variant to `(AgentReply, EventOutcome)` with correct `REASON_*`, then emit `"denied"`, return `Ok(reply)`.
3. `run_execution_plan` → on `Err(DatabaseFault)`, emit `"error"`, return `Ok(error reply)`.
4. Success → emit `"ok"` with `rows_count` / `affected_rows` from `DbPayload`.

Helper `_authz_to_reply_and_outcome` is the only place authz errors become user-visible text + audit reason codes.

### `build_runtime` (~74 LOC)

**File:** `bootstrap/container.py`

- **Required** kwargs: `verifier`, `policy_store`, `database` — no silent production fakes.
- Defaults only for infra without secrets: `PglastSqlAnalyzer`, `InProcessEventBus`, `SystemClock`, `Uuid4IdGenerator`.
- Wires four services into `InvokeAgentToolService`, returns `Runtime` dataclass holding ports + facade.

### `InProcessEventBus`

Sequential `await` per handler; handler exceptions swallowed (audit must not break invoke). P5 may add `ConsoleSink` subscriber here without changing emit service.

---

## Naming & readability

| Name | Why |
|------|-----|
| `PreAuthError` | Union alias — “before RequestContext, no audit trail yet” |
| `AuthzError` | Authorization + SQL guard + input validation, not identity |
| `ExecutionPlan` + `*Plan` dataclasses | DB intent as data, not strings |
| `run_execution_plan` | Verb + noun; single dispatch function |
| `sanitize_args` | Public, testable; documents security intent |
| `_authz_to_reply_and_outcome` | Private mapper; name encodes dual output |
| `Establish` / `Authorize` / `Emit` | One verb per service file — open file → know phase |

Each service file opens with a one-line module docstring describing inputs/outputs. Domain errors keep `invariant_id` + `message`; application does not invent parallel error enums.

---

## Function size & complexity

| File | LOC | Largest unit | Prime A11 |
|------|-----|--------------|-----------|
| `authorize_tool.py` | 141 | `_plan_select_rows` ~28 LOC; `_build_plan` ~20 | Split from monolithic `_build_plan` to pass cyclomatic ≤10 |
| `invoke_agent_tool.py` | 110 | `_authz_to_reply_and_outcome` ~44 | Acceptable: pure mapping table |
| `establish_request_context.py` | 58 | `execute` ~34 | Single linear async function |
| `emit_agent_action.py` | 50 | `emit` ~15 | Thin |
| `run_execution_plan.py` | 39 | 8 parallel branches + `assert_never` | Intentional central dispatch |
| `container.py` | 74 | `build_runtime` ~40 | Wiring only, no business logic |

No service file exceeds ~150 LOC. Raw SQL authorization stays in `AuthorizeToolService`; orchestration stays in `InvokeAgentToolService` — no “god invoke” class.

---

## Deliberate simplicity

- **No** generic plugin registry for tools — explicit `ToolName` branches + `assert_never`.
- **No** duplicate `EventOutcome` or event types in application layer.
- **No** default fake verifier/policy/database in `build_runtime` — tests and `scaffold.py` must pass explicit ports.
- **No** emit on pre-auth failure — avoids orphan audit rows without `agent_id`.
- **No** MCP/HTTP/asyncpg in P2 — pipeline testable with fakes only.
- **No** changes to `guard.py` — analyzer + authorize call existing P1 API.

---

## Maintainability (1-year view)

| Next phase | Touches | Leaves stable |
|------------|---------|---------------|
| **P3** | Replace scaffold `PassportVerifier` / `AgentPolicyStore` in `build_runtime` callers | All five services, `run_execution_plan`, emit, ZTA matrix |
| **P4** | `AsyncpgDatabaseGateway` implements existing port | Authorize plans, guard, invoke facade |
| **P5** | MCP handler calls `runtime.invoke_agent_tool.execute()`; optional `EventBus` subscriber | Domain + application unchanged |

**Extension points:** new tool = new `ToolName` + plan dataclass + branch in `_build_plan` + port method if needed + ZTA row.

**Risks:** `_authz_to_reply_and_outcome` must stay in sync with new `AuthzError` variants (mypy `assert_never` helps). Secret key list in `sanitize_args` may need env-specific keys — keep as explicit frozenset, not regex magic.

---

## Quality rubric

| Dimension | Score | Evidence |
|-----------|-------|----------|
| Readability | **Strong** | Pipeline readable top-to-bottom in `invoke_agent_tool.execute` (~25 LOC); each step file &lt;150 LOC |
| Naming | **Strong** | Phase verbs (`Establish`, `Authorize`, `Emit`); typed error unions at module scope |
| Small functions | **Strong** | Authorize split into `_plan_*` helpers after cyclomatic gate failure |
| No over-engineering | **Strong** | One dispatch function, one facade, four ports — no DI framework |
| Year-ahead maintenance | **OK** | P3/P4 are adapter swaps; tool catalog growth is manual but explicit (acceptable until tool count &gt; ~15) |

---

## ZTA matrix (contract)

| ID | Scenario | Expected |
|----|----------|----------|
| Z1 | Missing bearer | `Err(PassportMissing)`, 0 emits |
| Z2 | Invalid token | `Err(PassportInvalid)`, 0 emits |
| Z3 | Agent not on whitelist | `Err(AgentNotAllowlisted)`, 0 emits |
| Z4 | Missing capability | `Ok(denied)`, 1 emit, `REASON_CAPABILITY_DENIED` |
| Z5 | RO agent + write SQL | `Ok(denied)`, `REASON_STATEMENT_CLASS_DENIED` |
| Z6 | Invalid SQL | `Ok(denied)`, `REASON_SQL_PARSE_FAULT` |
| Z7 | Bad tool args | `Ok(denied)`, `REASON_TOOL_INPUT_INVALID` |
| Z8 | DB fault | `Ok(error)`, `REASON_DATABASE_FAULT` |
| Z9 | Happy SELECT | `Ok(ok)`, 1 emit with rows |
| Z10 | Policy store fault | `Err(PolicyStoreFault)`, 0 emits |

**File:** `tests/contract/test_zta_matrix.py` · **Gate:** `scripts/security/zta_matrix_gate.py`

---

## Test matrix

| ID | Covered in |
|----|------------|
| Z1–Z10 | `tests/contract/test_zta_matrix.py` |
| Establish / Authorize / Emit / Invoke unit | `tests/unit/application/services/test_*.py` |
| Fakes + wiring | `tests/fakes/*`, `tests/support/build_test_runtime.py` |
| prime_check subset | `scripts/tests_steps.py` → `P2_MATRIX` |

---

## Out of scope (deferred)

| Item | Phase |
|------|-------|
| `JsonAgentPolicyStore` disk load | **P3** |
| `LimePassportVerifier` / JWKS | **P3** |
| `AsyncpgDatabaseGateway` | **P4** |
| MCP tool handlers, `ConsoleSink` | **P5** |

---

## Verification

```text
cd Marketing/lime-postgres-mcp
uv sync --all-extras
uv run ruff check src tests
uv run mypy src
uv run pytest
uv run python -m scripts.prime_check
# pytest: 213 passed
# PASS=43 FAIL=0 SKIPPED=24
# prime_check: exit 0
# coverage_line/branch: 100.00%
# zta-matrix-gate: LIVE
```

---

## Evidence (sealed)

```text
PRIME-VERIFY-EVIDENCE
task: p2-invoke-agent-tool-zta-partial
tier: PRIME
adoption_mode: greenfield
isolation: package-only (Marketing/lime-postgres-mcp)
scope: InvokeAgentTool pipeline + Fake ports + ZTA Z1-Z10 + InProcessEventBus + build_runtime wiring
injection-fuzz: LIVE
zta-matrix-gate: LIVE
prime_check: exit 0
steps_live: 43
steps_skipped_adr: 24 (ADR-002)
coverage_line: 100.00%
coverage_branch: 100.00%
uncovered: NONE
next_mandatory_task: P3 JsonAgentPolicyStore + LimePassportVerifier
last_cmd: uv run python -m scripts.prime_check
```

---

## Next

**P4 done** — see [P4_REPORT.md](./P4_REPORT.md). Next mandatory: **P5** MCP presentation + ConsoleSink.
