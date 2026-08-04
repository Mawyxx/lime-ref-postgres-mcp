# LIME Ref Postgres MCP — P5 Ship Report

**Date:** 2026-08-04  
**Package:** `lime_ref_postgres_mcp` `0.1.0`  
**Path:** `Marketing/lime-postgres-mcp/` (package-only)  
**Tier:** PRIME · `adoption_mode: greenfield`  
**Status:** P5 complete — P5.1 process observability **done** (see [P5.1_REPORT.md](./P5.1_REPORT.md)); WebhookSink **out of scope**
**Report standard:** [README.md](./README.md)

---

## What landed

Thin Streamable HTTP MCP transport (official low-level `mcp.server.Server`) + `ConsoleSink` over the frozen P2–P4 pipeline. Invoke / Authorize / gateway / ZTA fakes / `InProcessEventBus` **unchanged**.

| Area | Paths | Role |
|------|-------|------|
| Auth | `presentation/mcp/auth.py` | `extract_bearer` (Request.headers first — Request is a Mapping) |
| Errors | `presentation/mcp/error_map.py` | `Result` → `CallToolResult` JSON `{"status","payload"}` |
| Specs | `presentation/mcp/tool_specs.py` | Exactly 8 `Tool` schemas; Authorize keys (`schema`/`table`/`sql`) |
| Handlers | `presentation/mcp/handlers/*` | Thin: args → `invoke_tool` → map |
| Server | `presentation/mcp/server.py` | `on_list_tools` / `on_call_tool`; `/mcp` only; serve lifespan |
| Sink | `subscribers/console_sink.py` | JSONL stdout; no payload/JWT/rows |
| Bootstrap | `bootstrap/container.py` | `subscribe_console_sink` on scaffold |
| Settings | `bootstrap/settings.py` | `LIME_MCP_BIND_HOST` / `LIME_MCP_PORT` |
| CLI | `__main__.py` | default = composition smoke; `serve` = uvicorn |
| Contract | `tests/contract/test_mcp_http.py` | In-process ASGI + fakes |
| E2E | `tests/e2e/test_mcp_streamable_http.py` | Loopback uvicorn + fakes |
| Gates | route-matrix, pytest-contract, pytest-e2e, e2e-only | LIVE; `ssrf-gate` stays SKIPPED (no outbound audit HTTP in showcase) |

**Locked contracts preserved:**

- P2 invoke pipeline / emit rules
- ZTA Z1–Z10 on fakes
- `InProcessEventBus` sequential await + swallow (deliberate P5 freeze)
- AsyncpgGateway port signatures; lazy pool until lifespan `open()`

---

## Implementation walkthrough

### `extract_bearer` (`presentation/mcp/auth.py`)

1. Resolve headers: prefer `.headers` when distinct from source (Starlette `Request` is a `Mapping` of path params).
2. Read `Authorization` case-insensitively.
3. Accept only `Bearer <nonempty>`; else `None` → `PassportMissing` (no event). Never log token.

### `map_to_mcp` (`presentation/mcp/error_map.py`)

1. `Ok(AgentReply)` → envelope status/payload verbatim; `is_error = (status != "ok")`.
2. `Err(PreAuth*)` → `status=error`, `{error, code}` from message/invariant_id; **no** `DomainError.context`.
3. Never raise `MCPError` for domain/pre-auth outcomes.

### Handlers + server dispatch

1. `on_call_tool` reads `ctx.request` → bearer → `ToolName` → handler.
2. Unknown tool → `CallToolResult(is_error=True)` with `mcp.unknown_tool` (not protocol `MCPError`).
3. Each handler ≤ few statements: `return await invoke_tool(...)`.

### Serve lifespan (composition edge)

1. If live `LimePassportVerifier`: `warmup(raise_on_failure=True)`.
2. If live `AsyncpgDatabaseGateway`: `open()`.
3. Yield (session manager runs).
4. `finally`: `database.close()` then `verifier.close()`.
5. Fail closed: JWKS/pool failure → process does not accept traffic.

### `ConsoleSink`

One compact JSON line + flush. Fields: `event_id`, `ts` (UTC Z), `agent_id`, `request.{tool,args}`, `status`, `outcome` (omit unset), `duration_ms`, `meta`. Forbidden: `payload`/`response`/`rows`/`result`/`body`.

---

## Naming & readability

- `extract_bearer` / `map_to_mcp` / `invoke_tool` name the transport boundary.
- Tool wire names = `ToolName` enum (SSOT with Authorize).
- `MCP_HTTP_PATH = "/mcp"` is the route-matrix constant.

---

## Function size & complexity

| File | LOC (approx) | Notes |
|------|--------------|-------|
| `auth.py` | ~45 | Header resolution edge for Request-as-Mapping |
| `error_map.py` | ~30 | Two branches Ok/Err |
| `server.py` | ~145 | Dispatch table + lifespan |
| Handlers | ~20 each | Thin wrappers |
| `console_sink.py` | ~70 | Record shaping only |

All presentation handlers under `handler_max_logic_lines` (15).

---

## Deliberate simplicity

- Did **not** use FastMCP / `MCPServer.@tool` — need per-call `ctx.request.headers`.
- Did **not** add REST/health/stdio.
- Did **not** rewrite EventBus to fire-and-forget (P5 freeze).
- Did **not** arm `ssrf-gate` (no outbound audit HTTP; WebhookSink out of scope for showcase).
- Did **not** put passport in tool args (ADR-001).

---

## Maintainability (1-year view)

| Next | Touch | Stable |
|------|-------|--------|
| **P5.1** | Process observability (ADR-003) | EventBus / ConsoleSink demo |
| **P6** | Keep CI green as package grows | Presentation surface |
| Integrator sinks | Fork: `bus.subscribe` (webhook/SIEM) — **not** maintainers | ConsoleSink shape / EventBus API |
| New tool | `ToolName` + Authorize plan + one handler + `tool_specs` | Invoke pipeline |

**Risk:** MCP SDK v2 snake_case / Streamable HTTP header attachment — pin `mcp` and keep contract tests as lock.

---

## Quality rubric

| Dimension | Score | Evidence |
|-----------|-------|----------|
| Readability | Strong | One dispatch site; handlers are one-liners |
| Naming | Strong | Authorize arg keys = wire schema |
| Small functions | Strong | handler-purity LIVE |
| No over-engineering | Strong | No OAuth middleware; Bearer only |
| Year-ahead maintenance | Strong | ConsoleSink demo stable; integrators add own sinks |

---

## Test matrix

| Cell | File |
|------|------|
| Auth | `tests/unit/presentation/mcp/test_auth.py` |
| error_map | `tests/unit/presentation/mcp/test_error_map.py` |
| tool_specs | `tests/unit/presentation/mcp/test_tool_specs.py` |
| Handlers | `tests/unit/presentation/mcp/test_handlers.py` |
| Server | `tests/unit/presentation/mcp/test_server.py` |
| Lifespan | `tests/unit/presentation/mcp/test_server_lifespan.py` |
| ConsoleSink | `tests/unit/subscribers/test_console_sink.py` |
| CLI serve | `tests/unit/test_main.py` |
| MCP HTTP contract | `tests/contract/test_mcp_http.py` |
| E2E Streamable HTTP | `tests/e2e/test_mcp_streamable_http.py` |
| ZTA (unchanged) | `tests/contract/test_zta_matrix.py` |

---

## Out of scope

| Item | Target |
|------|--------|
| WebhookSink | **out of scope** (integrator `bus.subscribe`) |
| `ssrf-gate` LIVE | N/A while no outbound audit HTTP |
| Stdio MCP | future ADR |
| REST /health | never (route-matrix) |
| EventBus rewrite | frozen |
| LIME prod ops of this package | never — GitHub showcase only |

---

## Verification commands

```bash
cd Marketing/lime-postgres-mcp
uv sync --all-extras
uv run ruff check src tests
uv run mypy src
uv run pytest                                          # unit+contract; excludes integration+e2e
uv run pytest tests/contract --no-cov -o addopts=
uv run pytest tests/e2e -m e2e --no-cov -o addopts=
uv run pytest tests/integration -m integration --no-cov -o addopts=
uv run python -m scripts.prime_check
```

Expected: unit 100% line+branch; contract/e2e/integration green; `prime_check` exit 0.

---

## Evidence (sealed)

```text
PRIME-VERIFY-EVIDENCE
task: p5-mcp-presentation-console-sink
tier: PRIME
adoption_mode: greenfield
stack: python
package: lime_ref_postgres_mcp
path: Marketing/lime-postgres-mcp
isolation: package-only
scope: Streamable HTTP MCP (/mcp) + ConsoleSink + serve CLI + low-level mcp.server.Server
injection-fuzz: LIVE
zta-matrix-gate: LIVE
pytest-integration: LIVE
pytest-contract: LIVE
pytest-e2e: LIVE
route-matrix-gate: LIVE
e2e-only-anti-pattern: LIVE
ssrf-gate: SKIPPED (ADR-002 flip_phase N/A-showcase)
prime_check: exit 0
steps_live: 48
steps_skipped_adr: 20 (ADR-002)
coverage_line: 100.00%
coverage_branch: 100.00%
uncovered: NONE
ci_workflow: .github/workflows/prime_check.yml
ast_gates: import-graph,di-purity,deterministic-runtime,anti-null,handler-purity,cyclomatic+file-size,anti-fork
next_mandatory_task: P5.1 process observability (ADR-003); then P6 CI green
last_cmd: uv run python -m scripts.prime_check
```

---

## Next

**P5.1** — process observability. **P6** — keep CI green.  
**Not ours:** WebhookSink / arm `ssrf-gate` — integrator/fork only (showcase package).
