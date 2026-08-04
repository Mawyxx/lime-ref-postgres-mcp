# ADR-002 — prime_check SKIPPED steps (Day 0.5)

**Status:** Accepted  
**Date:** 2026-07-31  
**Package:** `lime_ref_postgres_mcp` (package-local only)

## Context

AGENT-5 requires a full step catalog. Many Prime steps apply only **When** a surface exists (auth, Docker, SQL, HTTP). Forcing them LIVE before the surface exists would falsely block P1.

## Decision

Steps listed below return `SKIPPED(ADR-002)` until `flip_phase`. Removing a key from `skipped_steps` in `scripts/prime_check.config.yaml` arms the step (implement body if still stubbed).

| Step | flip_phase | Reason |
|------|------------|--------|
| `gitleaks-history` | extract/own-repo | Monorepo git history is out of package scope; LIVE `no-secrets` covers package tree |
| `sbom` | ~~P6/release~~ **LIVE since P6** | CycloneDX from `uv export --frozen` → `reports/sbom.cdx.json` |
| `injection-fuzz` | ~~P1b/P4~~ **LIVE since P1b** | Adversarial manifest + analyze→guard pytest |
| `ssrf-gate` | **N/A (showcase)** | No outbound HTTP client in this package. WebhookSink is **out of scope** for maintainers (integrators may add `bus.subscribe` in forks). JWKS is allowlisted via `LIME_JWKS_URL` inside SDK `TokenVerifier`. Keep SKIPPED permanently unless a fork introduces general outbound HTTP and arms the gate. |
| `zta-matrix-gate` | ~~P2~~ **LIVE since P2** | Contract Z1–Z10 via InvokeAgentToolService + Fake ports |
| `route-matrix-gate` | ~~P5~~ **LIVE since P5** | `/mcp` Streamable HTTP + exactly 8 `ToolName`s |
| `pytest-integration` | ~~P4~~ **LIVE since P4** | Testcontainers + `AsyncpgDatabaseGateway` |
| `pytest-contract` | ~~P5~~ **LIVE since P5** | MCP HTTP contract + ZTA |
| `pytest-e2e` | ~~P5~~ **LIVE since P5** | Loopback uvicorn Streamable HTTP smoke (fakes) |
| `pytest-property` | P2+ | Optional property suite later |
| `flaky-detector` | P2+ | Optional |
| `e2e-only-anti-pattern` | ~~P5~~ **LIVE since P5** | Auth/deny/error covered in unit/contract |
| `idempotency-matrix-gate` | when state-changing UC | No mutating UC yet |
| `fsm-transition-gate` | when FSM | No lifecycle FSM |
| `migration-path-only` | when migrations | No DB migrations |
| `schema-drift` | when migrations | No DB schema |
| `api-contract-drift` | when public API contract | No OpenAPI |
| `snapshot-contract` | when public contract | No snapshots |
| `docker-security` | when Dockerfile | No Docker |
| `compose-security` | when compose | No compose |
| `health-gate` | when probes | No /health |
| `tls-min-version` | when prod TLS config | No deploy TLS |
| `cert-forbidden-gate` | safety_profile | Not enabled |
| `concurrency-race-gate` | safety_profile | Not enabled |
| `clang-tidy` | safety_profile | N/A Python |
| `frontend-quality` | N/A | No frontend |
| `mutation-critical` | CRITICAL tier | Tier is PRIME |

## Consequences

- `--list` shows LIVE + `SKIPPED(ADR-002)`.
- Day 0.5 proves Empire scaffold; ZTA arms when `InvokeAgentTool` lands.
