# ADR-003 — Process Observability Contract

**Status:** Accepted (**shipped** — P5.1)  
**Date:** 2026-08-04  
**Related:** [PRD.md](./PRD.md) §8 · [TDD.md](./TDD.md) §9.6 · [ADR-001](./ADR-001-mcp-authentication-boundary.md) · Prime B03 / OWASP A09
**Risk:** PRIME — open-source reference presenting LIME; operators and contributors will read this code

---

## Context

Reference MCP already separates:

1. **Agent audit** — `AgentActionEvent` → `EventBus` → optional one-way sinks. This repo ships **`ConsoleSink` only** as an event-system demo. Webhook/SIEM sinks are **integrator/fork work**, not maintainers’ roadmap.  
2. **Auth boundary** — Bearer never in tool args / events / logs (ADR-001).

We still need **process observability**: what the *server* did (including pre-auth failures where no agent event exists). A half-measure (`print`, ad-hoc loggers, “ConsoleSink is enough”) is unacceptable for an open-source LIME **showcase** — readers will copy patterns. This package is not LIME production ops.

Prime **B03** requires the full triad on PRIME+: structured logs, **correlation_id**, and **metrics** on critical paths — not logs alone. OWASP **A09** forbids secrets/PII in logs.

HTTP surface of this package is intentionally **only** `/mcp` (route-matrix / ZTA story). Adding `/health` or `/metrics` would expand the attack/docs surface and fight the passport-first narrative.

---

## Decision

### 1. Three channels, never merged

| Channel | Purpose | Back-pressure into UC |
|---------|---------|------------------------|
| **A. Process log** | Server life (JSONL schema) | none |
| **B. Process metrics** | Counters + latency histograms | none |
| **C. Agent audit** | Post-whitelist accountability | none (sinks swallow errors) |

ConsoleSink remains **channel C only**. Removing it MUST NOT disable A/B.

### 2. One facade package

```text
bootstrap/observability/
  __init__.py      # public: configure_observability, get_logger, log, metrics, bind_context
  schema.py        # SCHEMA = lime.mcp.process_log.v1 + field constants
  redaction.py     # deny-list + value sanitizer
  context.py       # contextvars: request_id, agent_id, trace_id, parent_span_id
  logging.py       # JSON / console renderers
  metrics.py       # ProcessMetrics registry
  configure.py     # idempotent bootstrap wiring
```

**MUST NOT** call stdlib `logging.getLogger` for product events outside this package namespace.  
**MUST NOT** import observability from `domain/**` (Prime A05).

### 3. Versioned log schema

Every log record includes `"schema": "lime.mcp.process_log.v1"`.

- Default renderer: **JSON Lines** (`LIME_MCP_LOG_FORMAT=json`).  
- Optional: `console` key=value for humans — same fields.  
- Breaking field rename/remove → bump to `v2` + new ADR amendment.

### 4. Correlation

- Every inbound `tools/call` gets a `request_id` (Id port / uuid).  
- Bound via contextvars for the call duration; cleared in `finally`.  
- After passport verify: bind `agent_id`.  
- Same `request_id` → `AgentActionEvent.meta.request_id` when an event exists.  
- If HTTP carries W3C `traceparent`: parse and attach `trace_id` / `parent_span_id` to log context.  
- **v1 MUST NOT** require OpenTelemetry SDK at runtime (optional extras = future).

### 5. Metrics without new HTTP routes

In-process `ProcessMetrics`:

- counters + fixed-bucket histograms (PRD §8.5 catalog);
- `snapshot()` for unit tests and embedders;  
- `event=metrics.summary` on graceful shutdown.

**MUST NOT** add `/metrics` or `/health` in v1 (keeps route-matrix: only `/mcp`).  
Operators scrape **JSONL**; embedders use `snapshot()`. Future optional Prometheus route would be a separate ADR + route-matrix flip.

### 6. Redaction (enforced in facade)

Deny-list keys (case-insensitive):  
`authorization`, `bearer`, `bearer_token`, `token`, `passport`, `password`, `secret`, `api_key`, `postgres_url`, `payload`, `rows`, `response`, `body`, `result`, `jwt`.

Unknown non-scalar values → type name or `"<redacted>"`, never `repr` of secrets.

On `Err` log sites: `invariant_id` / `code` + safe ids only (A10).

### 7. Configure boundary

`configure_observability(...)` runs from composition root / `serve` **only**.  
Importing application modules MUST NOT install handlers as a side effect.

---

## Consequences

**Positive**

- Open-source readers get a copyable, tested observability pattern aligned with Prime B03.  
- Pre-auth failures are visible without polluting agent audit.  
- Channel C stays delete-safe.  
- `/mcp`-only surface preserved.

**Trade-offs**

- No Prometheus scrape endpoint in v1 (by design).  
- No full OTel exporter in v1 (traceparent parse only).  
- Contributors must wire facade on every new critical path (documented matrix).

**Rejected alternatives**

| Alternative | Why rejected |
|-------------|--------------|
| ConsoleSink as “the logger” | Misses pre-auth; couples ops to audit; delete breaks ops |
| Ad-hoc `logging` per module | No schema, no redaction SSOT, ugly for public repo |
| REST `/metrics` in v1 | Fights route-matrix / minimal surface; needs separate ADR |
| Log from `domain/**` | Violates A05 purity |
| Merge agent audit into process JSONL | Confuses accountability vs ops; breaks one-way sink story |

---

## Compliance map

| Prime / OWASP | How this ADR satisfies |
|---------------|------------------------|
| B03 logs | JSONL schema v1, structured fields |
| B03 correlation | `request_id` (+ optional W3C ids) ↔ event meta |
| B03 metrics | `ProcessMetrics` + shutdown summary |
| A05 | no obs I/O in domain |
| A10 | `invariant_id` + safe context on failures |
| A09 / OWASP A09 | deny-list redaction + pii-log-scan |
| A07 | design in PRD/TDD/this ADR before code |

---

## Implementation phase

**P5.1** — implement `bootstrap/observability`, wire call matrix, unit tests (schema, redaction, metrics snapshot, caplog), keep `prime_check` green / 100% coverage.
