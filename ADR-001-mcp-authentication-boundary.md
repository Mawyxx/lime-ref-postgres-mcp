# ADR-001 — MCP Authentication Boundary

**Status:** Accepted (design)  
**Date:** 2026-07-31  
**Related:** [PRD.md](./PRD.md) · [TDD.md](./TDD.md) · LIME `lime-mcp-server-sdk` (`TokenVerifier`)

---

## Context

Reference MCP пускает агентов по паспорту LIME в заголовке:

```http
Authorization: Bearer <lime_passport_jwt>
```

Транспорт MCP (HTTP / streamable HTTP / SSE) эволюционирует. Нужна зафиксированная **граница auth**, чтобы:

- presentation оставался тонким;
- application тестировался без живого HTTP;
- не смешивать «паспорт агента» с «учёткой Postgres».

---

## Decision

### 1. Где живёт auth context

| Стадия | Объект | Слой |
|--------|--------|------|
| Сырой вход | `InvokeAgentToolCommand.bearer_token: str \| None` | application/commands |
| После verify + whitelist | `RequestContext` (`AuthorizedAgent` + tool + args + `started_at`) | application/context |
| До успешного WL | `RequestContext` **не создаётся** | — |

**MUST NOT** хранить Bearer / raw JWT внутри `RequestContext`, event, logs.

### 2. Как headers попадают в команду

1. MCP HTTP request достигает presentation (`presentation/mcp/`).  
2. `auth.extract_bearer(request)` читает `Authorization` (case-insensitive), снимает префикс `Bearer `.  
3. Handler собирает `InvokeAgentToolCommand(bearer_token=…, tool=…, args=…)`.  
4. `InvokeAgentToolService` → `EstablishRequestContextService` → `PassportVerifier` (LIME JWKS).

Middleware/framework-specific wiring — только в presentation/bootstrap; **не** в domain.

### 3. Как тестировать без HTTP

| Уровень | Как |
|---------|-----|
| Unit application | Собрать `InvokeAgentToolCommand` вручную; Fake `PassportVerifier` / PolicyStore / DB / EventBus |
| Unit presentation | Вызвать `extract_bearer` на fake header map / stub Request |
| Contract ZTA | Тот же command-путь, без слушающего порта |
| E2E | **P5 mandatory local smoke:** loopback uvicorn Streamable HTTP + fakes (no live JWKS/Postgres); proves header → tool path. Live passport optional later |

**MUST:** ни один unit UC-тест не требует поднятого MCP socket.  
**P5:** package ships `tests/e2e/test_mcp_streamable_http.py` (`@pytest.mark.e2e`) as the local transport smoke gate.

### 4. WebSocket / session / stdio

| Транспорт | v1 |
|-----------|-----|
| Remote HTTP MCP (+ streamable/SSE as per SDK) | **in scope** — Bearer на каждом request |
| Stdio MCP | **out of scope** (нет HTTP headers) — отдельный ADR, если понадобится |
| Долгоживущая WS-сессия с auth только на handshake | **не опираемся** в v1: каждый tool call должен нести (или наследовать от request) проверяемый Bearer по контракту выбранного SDK; если SDK даёт session auth — presentation обязана прокинуть token в `Command` тем же путём |

### 5. Ошибки на границе

| Ситуация | Агенту | Событие |
|----------|--------|---------|
| Нет/битый Bearer | identity error | **нет** |
| Не в whitelist | allowlist error | **нет** |
| Дальше (capability/SQL/DB) | соответствующий error/result | **да** (без тела ответа) |

HTTP `401`/`403` vs MCP tool error — выбирает presentation по возможностям SDK; **семантика** выше SSOT.

### 6. Не смешивать секреты

| Секрет | Назначение |
|--------|------------|
| `Authorization: Bearer` (passport) | личность **агента** |
| `POSTGRES_URL` | учётка **сервиса** к БД |

Агент никогда не получает `POSTGRES_URL`.

---

## Consequences

- TDD: `extract_bearer` + Fake verifier = основной тест-контур.  
- Смена MCP transport SDK → правим только `presentation/mcp/*`, не policy/SQL/events.  
- Stdio / session-only auth требуют нового ADR, не «тихого» bypass паспорта.

---

## Rejected alternatives

| Alternative | Why rejected |
|-------------|--------------|
| Passport в args tool | дублирует JWT, светит в event.request, ломает MCP norm |
| Auth только на WS connect без per-call token | слабее для stolen session; усложняет тесты |
| Dev bypass без passport в prod codepath | запрещено PRD/TDD |
