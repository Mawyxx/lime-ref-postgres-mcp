# lime-ref-postgres-mcp

**English** · [Русский](./README.ru.md)

> An open-source **showcase of [LIME](https://lime.pics) agent identity** on a real resource: PostgreSQL behind [MCP](https://modelcontextprotocol.io/).

Agents do not share a generic database password. They arrive with a **LIME passport** (`Authorization: Bearer`), get checked against a local whitelist and capabilities, then use MCP tools against Postgres. After an authorized agent is recognized, the core emits one **audit event** — who called what, and how it ended — **without** copying the tool response body.

This repository is a **reference implementation**, not a production service operated by LIME. Fork it, study the pattern, run it against your own Postgres, and plug your own audit consumers if you need them.

---

## Why this exists

| Without named agent identity | With LIME on this door |
|------------------------------|-------------------------|
| One shared `POSTGRES_URL` / API key for every bot | Each agent is a **person** (`agent_id` from the passport) |
| Logs show “someone queried the DB” | Logs/events can say **which agent** did what |
| Hard to attach corporate audit / SIEM | EventBus is an extension point — subscribe your own sink |
| MCP demos often skip real auth | Same LIME passport model as other LIME-protected resources |

**Primary goal of this package:** make [LIME](https://lime.pics) technology tangible — passport → allowlist → action → event — on a concrete door (Postgres over MCP), so developers can see how agent identity works end-to-end.

Related LIME pieces:

- Platform & docs: [lime.pics](https://lime.pics)
- Agent client (issue MCP JWT with domain): [`lime-agents-sdk`](https://pypi.org/project/lime-agents-sdk/)
- Resource-server verify (JWKS / RS256): [`lime-mcp-server-sdk`](https://pypi.org/project/lime-mcp-server-sdk/) (this server wraps it)

---

## What it is / is not

| Is | Is not |
|----|--------|
| Open showcase of **LIME agent passport** on MCP → Postgres | LIME’s production product or hosted SaaS |
| Deny-by-default **whitelist + capabilities** | “One API key opens the whole DB” |
| Shipped **ConsoleSink** (demo of the event system) | Shipped webhook / SIEM exporters |
| Process observability (JSONL + metrics, ADR-003) | Mixing agent audit cards into process logs |
| Extractable package under this folder | Coupled to the rest of a monorepo runtime |

**Agent Bearer ≠ `POSTGRES_URL`.**  
The Bearer is the agent’s LIME passport. `POSTGRES_URL` is the **MCP service** database role — service credentials, not agent identity.

---

## How a call works

```
Agent (LIME passport)  -- Bearer + tools/call -->  MCP /mcp
         │
         ▼
   1. Verify JWT (JWKS from lime.pics, domain + aud pin)
         │ fail → error to agent, NO agent-action event
         ▼
   2. Whitelist (config/agents.json)
         │ unknown agent → error, NO agent-action event
         ▼
   3. Capabilities + SQL class guard
         │ denied → reply + agent-action event (denied)
         ▼
   4. Postgres (asyncpg)
         ▼
   5. Agent-action event (ok | error) → reply to agent
         │
         └── EventBus subscribers (ConsoleSink demo / your sink)
```

Process logs (`lime.mcp.process_log.v1`) always can record preauth failures and call lifecycle; **agent-action events** exist only after a allowlisted agent is established. See [ADR-003](./ADR-003-process-observability.md).

---

## Features

- **LIME passport gate** — `Authorization: Bearer` on every `tools/call`; verify via `lime-mcp-server-sdk`
- **Policy** — JSON whitelist, permissions `READ_SCHEMA` / `READ_DATA` / `WRITE_DATA` / `DDL` / `ADMIN`, `max_rows`, lazy reload by mtime
- **SQL defense** — pglast AST → statement-class guard (readonly vs write vs DDL)
- **Eight MCP tools** — schema / data / write / admin surface only on `/mcp`
- **Event system** — `AgentActionEvent` without response payload; `bus.subscribe(...)` for custom sinks
- **ConsoleSink** — optional JSONL cards on stdout (event-system demo)
- **Process observability** — structured logs + in-process metrics + `request_id` correlation
- **Quality gate** — package-local `prime_check` + CI workflow

---

## Quick start

**Requirements:** Python ≥ 3.12, [uv](https://github.com/astral-sh/uv). Docker only for integration tests.

```bash
cd lime-ref-postgres-mcp   # or clone this package as its own repo
uv sync --all-extras
cp .env.example .env            # fill LIME_* and POSTGRES_URL
# create config/agents.json from config/agents.example.json
# map real LIME agent_id (passport sub) → permissions

uv run python -m lime_ref_postgres_mcp serve
# → http://127.0.0.1:8000/mcp
```

From an agent worker, use **lime-agents-sdk** against that URL (OAuth mints a JWT with `{"domain": "<your pin>"}` matching `LIME_EXPECTED_DOMAIN`):

```python
from lime_agents import LimeAgent

async with LimeAgent(agent_token="...") as agent:
    tools = await agent.list_tools("http://127.0.0.1:8000/mcp")
    result = await agent.call_tool(
        "http://127.0.0.1:8000/mcp",
        "list_schemas",
        {},
    )
```

Composition check (no HTTP):

```bash
uv run python -m lime_ref_postgres_mcp
```

---

## MCP tools

| Tool | Capability |
|------|------------|
| `list_schemas` | `READ_SCHEMA` |
| `list_tables` | `READ_SCHEMA` |
| `get_table_schema` | `READ_SCHEMA` |
| `select_rows` | `READ_DATA` |
| `execute_readonly_query` | `READ_DATA` |
| `explain_query_plan` | `READ_DATA` |
| `execute_write_query` | `WRITE_DATA` |
| `get_database_stats` | `ADMIN` |

Passport goes in the HTTP header only — never in tool arguments.

---

## Agent event system (for integrators)

The core **emits** immutable `AgentActionEvent` values after an allowlisted agent is in context. It does **not** ship webhooks or SIEM connectors — by design. You attach consumers yourself.

### What you get on each event

- `agent_id`, `status` (`ok` | `denied` | `error`)
- `request` — tool name + args (no result rows / no agent reply body)
- `outcome` — reason codes, missing capabilities, statement class, row counts
- `meta` — e.g. `request_id`, `domain`
- `duration_ms`, `event_id`, `ts`

**Privacy rule:** full `SELECT` payloads must not leave through audit. Events are cards, not response mirrors.

### When there is no event

Missing / invalid passport, JWKS failure, or agent not on the whitelist → agent gets an error; **no** `AgentActionEvent` (there was no authorized actor). Process logs still record `preauth.fail`.

### Shipped demo: ConsoleSink

With `ENABLE_CONSOLE_EVENT_SINK=1` (default), bootstrap registers `ConsoleSink` — one JSON line per event on stdout. Turn it off if you only want your own subscribers.

### Add your own sink (logging elsewhere)

Any async callable that accepts `AgentActionEvent` works. Subscribe at composition time (after `build_scaffold_runtime` / on `runtime.event_bus`):

```python
from lime_ref_postgres_mcp.bootstrap.container import build_scaffold_runtime
from lime_ref_postgres_mcp.domain.auditing.agent_action_event import AgentActionEvent

async def forward_to_my_logger(event: AgentActionEvent) -> None:
    # Examples: write to your DB, push to a queue, call an internal API.
    # Do not put agent response bodies here — they are not on the event.
    await my_audit_store.write(
        agent_id=str(event.agent_id),
        tool=event.request.get("tool"),
        status=event.status,
        reason=(event.outcome.reason_code if event.outcome else None),
        request_id=(event.meta or {}).get("request_id"),
    )

runtime = build_scaffold_runtime()
runtime.event_bus.subscribe(forward_to_my_logger)
# then serve ASGI from this runtime (same pattern as `serve`)
```

**Rules of the road**

1. Sink is **one-way**: read the event; do not call back into invoke/authorize.
2. Sink errors are swallowed by the bus — they must **not** change the tool `Result` returned to the agent.
3. Prefer idempotent, fast handlers; offload heavy work to a queue inside your sink.
4. Process observability (`bootstrap.observability`) is a **different** channel from agent events — don’t overload one with the other.

`ConsoleSink` source: [`subscribers/console_sink.py`](./src/lime_ref_postgres_mcp/subscribers/console_sink.py).  
Port: [`application/ports/events.py`](./src/lime_ref_postgres_mcp/application/ports/events.py).

---

## Configuration

Copy [`.env.example`](./.env.example). Important variables:

| Variable | Required | Role |
|----------|----------|------|
| `LIME_EXPECTED_DOMAIN` | yes | Hostname pin on the MCP JWT (`domain` claim) |
| `LIME_JWKS_URL` | yes | JWKS (default lime.pics well-known) |
| `LIME_EXPECTED_AUD` | no | default `mcp` |
| `POSTGRES_URL` | yes | Service DB URL (lazy pool) |
| `AGENTS_POLICY_PATH` | no | default `./config/agents.json` |
| `POLICY_RELOAD_TTL_SECONDS` | no | default `60` |
| `ENABLE_CONSOLE_EVENT_SINK` | no | default on — demo agent-action JSONL |
| `LIME_MCP_LOG_*` / `LIME_MCP_METRICS` | no | process observability (ADR-003) |
| `LIME_MCP_BIND_HOST` / `LIME_MCP_PORT` | no | `serve` bind (default `127.0.0.1:8000`) |
| `LIME_MCP_ALLOWED_HOSTS` | no | DNS-rebinding Host allowlist (comma-separated; default bind host/loopback) |

Policy shape: [`config/agents.example.json`](./config/agents.example.json).

There is **no** `WEBHOOK_URL` and no WebhookSink in this package.

---

## Verify / quality

```bash
uv run ruff check src tests
uv run mypy src
uv run pytest
uv run pytest tests/integration -m integration --no-cov -o addopts=

uv run python -m scripts.prime_check
uv run python -m scripts.prime_check --list
```

Nested CI: [`.github/workflows/prime_check.yml`](./.github/workflows/prime_check.yml) (extract-to-own-repo ready).

---

## Documentation map

| Doc | Content |
|-----|---------|
| [PRD.md](./PRD.md) | Product intent, access model, event rules |
| [TDD.md](./TDD.md) | Architecture, layers, module map |
| [ADR-001](./ADR-001-mcp-authentication-boundary.md) | Auth boundary on MCP |
| [ADR-003](./ADR-003-process-observability.md) | Process logs + metrics + correlation |
| [docs/verification/](./docs/verification/) | Phase reports (Day0 → P6) |

---

## Layout

```
src/lime_ref_postgres_mcp/
  domain/           # policy, SQL guard, AgentActionEvent (pure)
  application/      # invoke / authorize / emit ports
  infrastructure/   # JWKS verify, JSON policy, asyncpg, EventBus
  presentation/mcp/ # Streamable HTTP /mcp
  subscribers/      # ConsoleSink (demo)
  bootstrap/        # settings, container, process observability
config/             # agents.example.json
scripts/prime_check # package quality gate
tests/
```

---

## Status

Showcase sealed through **P6** (CI green + SBOM). Intended as public reference code for LIME agent identity on MCP → Postgres.

**Maintainers do not** operate this as LIME production, and do not ship outbound webhook sinks.

---

## License

See package metadata in [`pyproject.toml`](./pyproject.toml).
