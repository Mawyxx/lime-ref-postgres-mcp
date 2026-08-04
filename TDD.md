# TDD — Reference MCP: агент с паспортом LIME → PostgreSQL

**Тип документа:** Technical Design Document (реализация ещё не написана — это целевая архитектура)  
**Статус:** Draft v1  
**Связанные артефакты:** [PRD.md](./PRD.md) · [Mawyxx Prime V5.6](../../docsN/Mawyxx%20Prime%20V5.6.md)  
**Стек (Project Skin):** Python 3.12+ · official `mcp` SDK · `asyncpg` · `pglast` (libpg_query) · LIME JWKS verify (контракт lime.pics / `lime-mcp-server-sdk`)  
**Risk tier (Prime A01):** **PRIME** — machine auth, ZTA на каждый tool, SQL surface, accountability через события  

---

## 0. Зачем этот TDD (критика стандарта → вывод)

Prime V5.6 требует **Empire Engine** (слои, порты, ZTA, cohesion, test taxonomy + Anti-N/A, intent lock, blast radius, Law→Gate, 100% coverage на PRIME), но **Project Skin** — родной для пакета, без навязывания «чужого» DDD-ритуала ради ритуала.

| Prime outcome | Как применяем здесь | Что сознательно не тянем |
|---------------|---------------------|---------------------------|
| A05 Layer law | Core ↛ I/O; thin MCP transport | CQRS, лишние bounded contexts |
| A06 DI & ports | Все I/O за Protocol; Clock/Id inject | Service locator, globals |
| A07 Design-first | Этот TDD → тесты → код | «Сначала скрипт, потом архитектура» |
| A02 / A29 ZTA | Authz на **каждый** tool call | Trust localhost / «internal MCP» |
| A10 Explicit errors | `Result[T, Err]` + named variants | `None` / голый exception как бизнес-исход |
| A18 OWASP injection | AST guard + single-statement + parameterized + READ ONLY txn + least-privilege role | Text/regex SQL «filter»; multi-statement string exec |
| A08 Anti-fork | Один pipeline вызова tool | Второй «быстрый» путь без паспорта |
| B03 Events | Domain/application fact → bus; sinks снаружи (односторонние) | `print` в tool как «лог агента»; sink → pipeline |
| B03 Observability | `bootstrap/observability` — logs **+** metrics **+** correlation; schema v1; ADR-003 | Путать ConsoleSink с process obs; log в `domain/**`; `/metrics` HTTP в v1 |
| B07 YAGNI | Policy v1 = whitelist + permissions + max_rows; SQL AST walk без table ACL / cost model | Multi-tenant PG; per-table ACL |

**Продуктовый инвариант (из PRD):** сначала личность агента LIME, потом дверь к ресурсу. Postgres — showcase-ресурс за тем же пропуском. Пакет — **open-source demo на GitHub**, не прод LIME.

---

## 1. Цели архитектуры

1. Один оркестрационный путь: `Bearer → verify → whitelist → permissions → (SQL class) → DB → event? → MCP response`.  
2. Ядро не знает про MCP JSON-RPC, asyncpg, stdout webhook-sink.  
3. Событие — факт application-слоя; **не** функционал консоли/webhook.  
4. **Process observability** — публичный контракт жизни сервера (Prime B03 / ADR-003): JSONL schema + metrics + correlation; отделена от agent audit; domain без obs I/O.  
5. Тестируемость: Fake verifier / Fake DB / Recording EventBus / FixedClock / metrics.snapshot — без сети.  
6. Import-graph: `domain` и `application` не импортируют `mcp`, `asyncpg`, `httpx`, `pglast` (парсер — только `infrastructure/sql`).  
   Facade `bootstrap.observability` **разрешён** в application/infrastructure/presentation/bootstrap; **запрещён** в `domain/**`.

---

## 2. Контекст системы (C4-L1)

```text
┌─────────────┐   HTTPS MCP + Authorization: Bearer <passport>
│ Agent /     │ ──────────────────────────────────────────────►
│ MCP Client  │
└─────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│  lime-ref-postgres-mcp  (этот пакет)      │
│  presentation → application → domain      │
│         ↓ ports                           │
│  infra: JWKS verify · PG · EventBus · (adapters via observability facade)
└───────────────────────────────────────────┘
        │                         │
        ▼                         ▼
┌───────────────┐         ┌─────────────────┐
│ lime.pics     │         │ PostgreSQL      │
│ JWKS (cache)  │         │ (ресурс-дверь)  │
└───────────────┘         └─────────────────┘
        │
        ▼ (опционально, composition root — one-way)
┌───────────────────────────┐
│ Event subscribers (optional)│
│ ConsoleSink = shipped demo  │  ← только читают AgentActionEvent
│ (webhook etc. = integrator) │
└───────────────────────────┘
        │
        ▼ (всегда при serve — не subscriber)
┌───────────────────────────────────────────┐
│ bootstrap/observability                   │
│ JSONL process log · ProcessMetrics        │  ← ADR-003 / PRD §8
└───────────────────────────────────────────┘
```

---

## 3. Логические слои (роли Prime A05)

| Роль | Пакет | Ответственность |
|------|-------|-----------------|
| **Domain** | `lime_ref_postgres_mcp.domain` | VO, policy-правила, типы события, ошибки, **без I/O** |
| **Application** | `…application/{commands,services,ports}` | UC-оркестрация; команды; порты по зависимостям |
| **Infrastructure** | `…infrastructure` | JWKS/passport, asyncpg, JSON policy file, in-process bus |
| **Presentation** | `…presentation.mcp` | MCP server: Bearer → DTO → invoke → map Result |
| **Composition** | `…bootstrap` / `__main__` | DI wiring, регистрация demo-sinks, lifespan |

**Закон импортов (MUST для `import-graph-gate`):**

```text
presentation  → application, domain
application   → domain, (ports только как Protocol в application/ports)
infrastructure → application.ports, domain
bootstrap     → всё (единственное место concrete wiring)
domain        → ∅ внешних I/O-пакетов
```

---

## 4. Структура папок (целевая)

Пакет — **standalone greenfield** (`Marketing/lime-postgres-mcp/src/...`).  
**Изоляция (жёстко):** весь код, тесты, docs, `prime_check`, ADR, verification reports, CI workflow для этого MCP — **только** под `Marketing/lime-postgres-mcp/`. **MUST NOT** импортировать `srcN`, править root `scripts/prime_check.py`, писать артефакты в `docsN/`.  
**Правило роста:** один use-case = пара `commands/<name>.py` + `services/<name>.py`; порты режутся по bounded dependency, не сваливаются в один `ports.py` / `dto.py` / `invoke_tool.py`.

Когда появятся `RotateAgentKey`, `InspectAgent`, `RegisterTool`, `PolicyUpdate` — добавляются **новые файлы** в `commands/` и `services/`, а не раздувается один god-module.

```text
lime-postgres-mcp/
├── PRD.md
├── TDD.md
├── pyproject.toml
├── README.md
├── config/
│   └── agents.example.json
├── src/
│   └── lime_ref_postgres_mcp/
│       ├── __init__.py
│       ├── __main__.py
│       │
│       ├── bootstrap/                         # composition root only
│       │   ├── __init__.py
│       │   ├── container.py                   # build_runtime() → wire DI
│       │   ├── settings.py                    # env → Settings
│       │   └── observability/                 # SSOT process obs (ADR-003)
│       │       ├── __init__.py                # public facade
│       │       ├── schema.py                  # lime.mcp.process_log.v1
│       │       ├── redaction.py               # deny-list sanitizer
│       │       ├── context.py                 # contextvars correlation
│       │       ├── logging.py                 # JSONL / console renderers
│       │       ├── metrics.py                 # ProcessMetrics
│       │       └── configure.py               # configure_observability()
│       │
│       ├── domain/                            # no I/O (Prime A05)
│       │   ├── __init__.py
│       │   ├── common/
│       │   │   ├── result.py                  # Result[Ok, Err]
│       │   │   └── errors.py                  # sealed DomainError hierarchy
│       │   ├── agent/
│       │   │   └── agent_id.py
│       │   ├── access/
│       │   │   ├── capability.py              # ToolCapability
│       │   │   ├── authorized_agent.py        # AuthorizedAgent (post whitelist)
│       │   │   └── policy.py                  # AgentPolicy, PolicyDocument
│       │   ├── catalog/
│       │   │   └── tool_catalog.py            # ToolName → required capability
│       │   ├── sql/
│       │   │   ├── types.py                   # SqlStatementClass
│       │   │   ├── analysis.py                # SqlAnalysis VO (class + flags)
│       │   │   └── guard.py                   # SqlGuardDecision (pure; no pglast)
│       │   └── auditing/
│       │       └── agent_action_event.py      # immutable event VO
│       │
│       ├── application/
│       │   ├── __init__.py
│       │   ├── context/                       # per-request aggregates (frozen)
│       │   │   ├── __init__.py
│       │   │   ├── request_context.py         # RequestContext
│       │   │   ├── agent_reply.py             # AgentReply → MCP only (full payload)
│       │   │   └── event_outcome.py           # EventOutcome card → event only (no payload)
│       │   ├── ports/
│       │   │   ├── __init__.py
│       │   │   ├── identity.py
│       │   │   ├── policy.py
│       │   │   ├── database.py
│       │   │   ├── sql_analyzer.py           # SqlAnalyzer → SqlAnalysis (no pglast in domain)
│       │   │   ├── events.py
│       │   │   └── clock.py
│       │   ├── commands/
│       │   │   ├── __init__.py
│       │   │   └── invoke_agent_tool.py       # InvokeAgentToolCommand
│       │   │   # future: rotate_agent_key.py, inspect_agent.py, …
│       │   └── services/
│       │       ├── __init__.py
│       │       ├── invoke_agent_tool.py       # InvokeAgentToolService
│       │       ├── establish_request_context.py  # passport+WL → RequestContext|Err
│       │       ├── authorize_tool.py          # capability + SQL guard on ctx
│       │       └── emit_agent_action.py       # emit(ctx, EventOutcome) — never AgentReply.payload
│       │       # future: rotate_agent_key.py, …
│       │
│       ├── infrastructure/                    # adapters implementing ports
│       │   ├── __init__.py
│       │   ├── identity/
│       │   │   └── lime_passport_verifier.py
│       │   ├── policy/
│       │   │   └── json_agent_policy_store.py
│       │   ├── postgres/
│       │   │   ├── pool.py
│       │   │   └── asyncpg_database_gateway.py
│       │   ├── sql/
│       │   │   └── pglast_sql_analyzer.py    # libpg_query walk → SqlAnalysis
│       │   ├── events/
│       │   │   └── inprocess_event_bus.py
│       │   └── clock/
│       │       ├── system_clock.py
│       │       └── uuid_id_generator.py
│       │
│       ├── presentation/                      # transport only — thin
│       │   └── mcp/
│       │       ├── __init__.py
│       │       ├── server.py                  # register tools, lifespan
│       │       ├── auth.py                    # extract Bearer → str|None
│       │       ├── error_map.py               # DomainError → MCP payload
│       │       └── handlers/                  # 1 handler group / surface; call services only
│       │           ├── __init__.py
│       │           ├── schema_tools.py        # list_schemas|tables|get_table_schema
│       │           ├── data_tools.py          # select / readonly / write
│       │           └── admin_tools.py         # explain / stats
│       │
│       └── subscribers/                       # NOT event core — optional sinks
│           ├── __init__.py
│           └── console_sink.py                # shipped DEMO of agent events
│           # webhook_sink.py — NOT in this repo; integrators bus.subscribe(...)
│
└── tests/
    ├── unit/
    │   ├── domain/
    │   │   ├── access/
    │   │   ├── sql/                         # guard rules on SqlAnalysis fixtures
    │   │   └── catalog/
    │   ├── infrastructure/
    │   │   └── sql/                         # pglast analyzer + adversarial payloads
    │   ├── application/
    │   │   ├── services/
    │   │   └── commands/
    │   └── infrastructure/                    # fakes optional here
    ├── contract/
    │   └── test_zta_matrix.py
    └── integration/
        └── test_postgres_gateway.py
```

### 4.1 Почему так (а не плоский `invoke_tool.py` + `dto.py` + `ports.py`)

| Плоский anti-pattern | Проблема при росте | Целевая форма |
|----------------------|--------------------|---------------|
| `application/invoke_tool.py` | Следующий UC → `invoke_tool_v2` / god-file | `services/<use_case>.py` |
| `application/dto.py` | Все команды в одной куче | `commands/<use_case>.py` рядом с сервисом |
| `application/ports.py` | 15 протоколов в одном файле | `ports/<dependency>.py` |
| `domain/*.py` мешком | Смешение policy/sql/event | `domain/<concept>/` |
| `tool_handlers.py` на всё | Толстый presentation | `handlers/<surface>.py` |

**Связка use-case (обязательная конвенция):**

```text
commands/invoke_agent_tool.py   →  данные команды
services/invoke_agent_tool.py   →  оркестрация
ports/*                         →  зависимости сервиса (inject в ctor)
```

Тот же шаблон для будущего:

```text
commands/rotate_agent_key.py  ↔  services/rotate_agent_key.py
commands/inspect_agent.py     ↔  services/inspect_agent.py
commands/register_tool.py     ↔  services/register_tool.py
commands/update_policy.py     ↔  services/update_policy.py
```

### 4.2 Import law (коротко)

```text
presentation  → application.services, application.commands, domain.common.errors
application   → domain, application.ports   (не infrastructure)
infrastructure → application.ports, domain
subscribers   → domain.auditing (event VO), не services
bootstrap     → всё concrete
domain        → только stdlib / typing
```

**Почему `subscribers/` не в `application`:** PRD — консоль не функционал ивентов; только `EventBus.subscribe` в `bootstrap`. Односторонние: emit → sink; sink **не** зовёт services обратно. В репо ship’им только `ConsoleSink` как демо системы ивентов; webhook/SIEM — зона интегратора (форк), не maintainers showcase.

**Почему `observability/` в `bootstrap/`:** process concern + единый `configure` при `serve` + публичный open-source контракт (ADR-003). Вызовы facade — из application/infrastructure/presentation. Domain без I/O (A05). Это **не** subscriber и не agent audit (PRD §8; события агента — PRD §7).

---

## 5. Domain — типы и инварианты

### 5.1 Value objects

| Тип | Смысл | Инварианты |
|-----|--------|------------|
| `AgentId` | `str` newtype / frozen | non-empty; из JWT `sub` |
| `ToolCapability` | enum | `READ_SCHEMA` \| `READ_DATA` \| `WRITE_DATA` \| `DDL` \| `ADMIN` |
| `ToolName` | enum / frozen str | совпадает с MCP tool name |
| `SqlStatementClass` | enum | `READ` \| `DML` \| `DDL` \| `ADMIN` \| `UNKNOWN` |
| `AgentPolicy` | `agent_id` + `frozenset[ToolCapability]` | только из whitelist |
| `PolicyDocument` | `max_rows` + `agents` map | `max_rows >= 1` |
| `AgentActionEvent` | frozen dataclass | см. §8; immutable |
| `AuthorizedAgent` | `agent_id` + `permissions` + optional `domain` | **только** после passport+whitelist OK |

**Зачем не `mode=read|write`:** write неоднороден. `WRITE_DATA` (DML) ≠ `DDL` (DROP/ALTER/…). Грубый write давал бы DROP вместе с INSERT.

### 5.1.1 Pipeline aggregates — не размазывать поля

Сейчас легко расползтись: `agent_id`, `request_id`, `domain`, `tool`, `clock` передаются россыпью между шагами.  
Prime A05/A17: **одна ответственность + явные VO**. Вводим frozen-агрегаты на границах шагов.

#### A) До auth — только команда (уже есть)

`InvokeAgentToolCommand` — сырой вход transport/application.  
**MUST NOT** называться `RequestContext`: там ещё нет `AuthorizedAgent`.

#### B) После passport + whitelist — `RequestContext`

```python
@dataclass(frozen=True)
class RequestContext:
    request_id: str
    agent: AuthorizedAgent          # agent_id + permissions + domain
    tool: ToolName
    args: Mapping[str, Any]         # уже без secrets; passport никогда здесь
    started_at: datetime            # Clock.now_utc() в момент успешного establish
```

| Поле | Откуда | Зачем в одном объекте |
|------|--------|------------------------|
| `request_id` | command / IdGenerator | correlation в event.meta и логах процесса |
| `agent` | verify + policy resolve | единственный носитель личности+permissions |
| `tool` + `args` | command | что запросили (для guard + event.request) |
| `started_at` | Clock один раз | `duration_ms` без повторных `now()` |

**Правила:**

- Создаётся **только** в `EstablishRequestContextService` после успешного WL.  
- До этого `RequestContext` **не существует** → emit невозможен (PRD).  
- Все шаги authorized-path принимают `ctx: RequestContext`, а не россыпь аргументов.  
- Immutable: следующий шаг не мутирует — возвращает `Result` / новый VO (`SqlGuardDecision`, `AgentReply`).

Путь: `application/context/request_context.py`.

#### C) Ответ агенту vs карточка в событии — **разные VO**

Полный ответ модели и audit-заметка **не должны** быть одним объектом (утечка PII через webhook).

```python
@dataclass(frozen=True)
class AgentReply:
    status: Literal["ok", "error", "denied"]
    payload: Any          # ПОЛНЫЙ ответ → только MCP tool result

@dataclass(frozen=True)
class EventOutcome:
    reason_code: str | None = None
    missing_capabilities: tuple[str, ...] = ()
    statement_class: str | None = None
    rows_count: int | None = None
    affected_rows: int | None = None
```

| VO | Куда | Содержит тело ответа агенту? |
|----|------|------------------------------|
| `AgentReply` | presentation → MCP | **да** |
| `EventOutcome` | `EmitAgentActionService` → `AgentActionEvent.outcome` | **нет** |

**MUST NOT:** класть `AgentReply.payload` / `rows` / LLM error text в `AgentActionEvent`.  
**MUST:** `build_event_outcome(reply, …)` извлекает только счётчики/коды; payload отбрасывается.

Пути: `application/context/agent_reply.py`; `EventOutcome` SSOT = `domain/auditing/event_outcome.py`.

#### D) Решение SQL-guard — `SqlGuardDecision`

```python
@dataclass(frozen=True)
class SqlGuardDecision:
    statement_class: SqlStatementClass
    allowed: bool
    required_capability: ToolCapability | None
    reason_code: str | None           # e.g. statement_class_denied
```

Pure из `domain/sql/guard.py` на основе `SqlAnalysis` + tool + `ctx.agent.permissions` (без парсера).

#### E) Зачем ещё аналоги (критический набор, не расползание)

| Aggregate | Когда появляется | Зачем | Файл |
|-----------|------------------|--------|------|
| `RequestContext` | после WL | склеить request_id/agent/tool/time | `application/context/request_context.py` |
| `AgentReply` | исход для модели | полный payload → **только MCP** | `application/context/agent_reply.py` |
| `EventOutcome` | исход для аудита | коды/счётчики → **только event** | `domain/auditing/event_outcome.py` |
| `SqlGuardDecision` | raw SQL tools | явный allow/deny класса SQL | `domain/sql/guard.py` |
| `CapabilityDecision` | каждый tool | required cap ∈ permissions? | `domain/access/capability_check.py` |
| `PolicySnapshot` | на establish | immutable policy на запрос | establish service |
| `ExecutionPlan` | после allow | gateway method + clamped args | `application/context/execution_plan.py` |

**SHOULD NOT:** один VO «и агенту и в event» с полным payload.  
**SHOULD:** `RequestContext` + раздельные `AgentReply` / `EventOutcome`.

**Антипаттерн:** «частичный context» с `agent_id: str | None` до auth — тогда снова silent null (A10). Pre-auth = `Command` + `Result[RequestContext, PreAuthError]`.

### 5.2 Domain errors (именованные, A10)

| Err | Когда | Event? |
|-----|--------|--------|
| `PassportMissing` | нет Bearer | нет |
| `PassportInvalid` | verify/claims fail | нет |
| `AgentNotAllowlisted` | `agent_id` ∉ policy | нет |
| `CapabilityDenied` | нет required capability на tool | **да** |
| `StatementClassDenied` | SQL-класс не покрыт permissions / запрещён на tool | **да** |
| `ToolInputInvalid` | bad args | да, если уже `AuthorizedAgent` |
| `DatabaseFault` | ошибка PG (masked) | да |
| `PolicyStoreFault` | не прочитали config | process/health; не agent-event |

**MUST NOT:** `return None` как «отказано».  
**MUST:** `Result[ToolOutcome, DomainError]` из application entry.

### 5.3 Policy resolve (pure)

```text
DEFAULT_PERMISSIONS = {READ_SCHEMA, READ_DATA}   # если поле permissions отсутствует

PolicyDocument.resolve(agent_id) -> Result[AgentPolicy, AgentNotAllowlisted]
AgentPolicy.has(cap: ToolCapability) -> bool
AgentPolicy.has_all(required: set[ToolCapability]) -> bool
PolicyDocument.clamp_limit(requested) -> int
```

Никакого I/O в `domain.policy`. Пустой `permissions: []` → `has(*)` всегда false → все tools `CapabilityDenied` + event.

### 5.4 Tool catalog (SSOT) — tool → required capability

`domain/catalog/tool_catalog.py`:

| ToolName | Required capability | Примечание |
|----------|---------------------|------------|
| `list_schemas` | `READ_SCHEMA` | |
| `list_tables` | `READ_SCHEMA` | |
| `get_table_schema` | `READ_SCHEMA` | |
| `select_rows` | `READ_DATA` | parameterized |
| `execute_readonly_query` | `READ_DATA` | + SQL class MUST be `READ` |
| `explain_query_plan` | `READ_DATA` | |
| `execute_write_query` | `WRITE_DATA` | + SQL class MUST be `DML` only |
| `get_database_stats` | `ADMIN` | |

v1: **нет** MCP tool под `DDL`. Capability `DDL` в конфиге валидна, но без tool не используется; DDL-текст в `execute_write_query` → `StatementClassDenied`.

### 5.5 SQL analysis (SSOT, AST, fail-closed)

**Запрещено как SSOT:** regex / «первое ключевое слово» / best-effort text classifier.  
**Обязательно:** парсер PostgreSQL (`pglast` / libpg_query) + полный walk AST.

#### Разделение слоёв

| Что | Где | Зависимость |
|-----|-----|-------------|
| `SqlStatementClass`, `SqlAnalysis`, `SqlGuardDecision` | `domain/sql/*` | pure; **нет** `pglast` |
| `SqlAnalyzer.analyze(sql) -> Result[SqlAnalysis, SqlParseFault]` | `application/ports/sql_analyzer.py` | Protocol |
| `PglastSqlAnalyzer` | `infrastructure/sql/pglast_sql_analyzer.py` | `pglast` |

```python
@dataclass(frozen=True)
class SqlAnalysis:
    statement_class: SqlStatementClass     # READ|DML|DDL|ADMIN|UNKNOWN
    statement_count: int
    top_level_kind: str                    # e.g. SelectStmt, DeleteStmt
    has_modifying_cte: bool
    has_txn_control: bool                  # BEGIN/COMMIT/ROLLBACK/…
    is_explain_analyze: bool
    # … иные флаги по мере нужды guard
```

#### Алгоритм класса (после parse)

1. `statement_count != 1` → `UNKNOWN`.  
2. Любой txn-control узел → `UNKNOWN`.  
3. Walk **всех** узлов: собрать set категорий (READ_NODE / DML_NODE / DDL_NODE / ADMIN_NODE).  
4. Приоритет (жёстче побеждает): `ADMIN` > `DDL` > `DML` > `READ`.  
   - `WITH (DELETE…) SELECT` → есть DML_NODE → **`DML`**, не READ.  
5. Parse error → `UNKNOWN`.  
6. Сомнение / неизвестный опасный узел → `UNKNOWN`.

| Class | Capability (если tool допускает класс) |
|-------|----------------------------------------|
| `READ` | `READ_DATA` |
| `DML` | `WRITE_DATA` |
| `DDL` | `DDL` |
| `ADMIN` | `ADMIN` |
| `UNKNOWN` | **deny** |

#### Tool ↔ analysis (v1)

| Tool | Allow |
|------|-------|
| `execute_readonly_query` | `statement_class == READ` only |
| `explain_query_plan` | `READ` and not (`is_explain_analyze` with nested mutate) |
| `execute_write_query` | `top_level_kind ∈ {InsertStmt, UpdateStmt, DeleteStmt}` **и** class ⊆ DML (нет DDL/ADMIN); **deny** если корень `SelectStmt` даже при `has_modifying_cte` |

`AuthorizeToolService`: `analyzer.analyze` → `guard(tool, analysis, permissions)` → `SqlGuardDecision`.

#### Adversarial MUST (infra unit, без БД)

Минимум (ожидание = deny / не-READ где указано):

1. `WITH x AS (DELETE FROM t RETURNING *) SELECT * FROM x;` → class `DML`  
2. `COMMIT; DROP SCHEMA public CASCADE;` → `UNKNOWN` / multi-stmt  
3. `SELECT 1; SELECT 2;` → multi-stmt  
4. `SELECT * FROM t FOR UPDATE;` → не чистый READ (deny на readonly)  
5. `SELECT * INTO new_t FROM t;` → не READ  
6. `EXPLAIN ANALYZE DELETE FROM t;` → deny на explain/readonly  
7. `COPY (SELECT 1) TO PROGRAM '…';` → ADMIN/UNKNOWN deny  
8. `WITH x AS (INSERT INTO logs VALUES (1) RETURNING *) SELECT * FROM x;` → `DML`; write-tool deny (не top-level DML)  
9. Plain `INSERT INTO t VALUES (1)` → allow write-tool при `WRITE_DATA`  
10. `DROP TABLE t;` → deny write-tool (`statement_class_denied`)

Расширять suite при нахождении bypass (как bettyguo/mcp-postgres).

---

## 6. Ports (`application/ports/*`) — A06

Не один файл: **один файл = одна внешняя зависимость**.

| Файл | Protocol |
|------|----------|
| `ports/identity.py` | `PassportVerifier` |
| `ports/policy.py` | `AgentPolicyStore` |
| `ports/database.py` | `DatabaseGateway` |
| `ports/sql_analyzer.py` | `SqlAnalyzer` |
| `ports/events.py` | `EventBus` |
| `ports/clock.py` | `Clock`, `IdGenerator` |

```text
# ports/identity.py
Protocol PassportVerifier:
    async verify(bearer_token: str) -> Result[PassportClaims, PassportInvalid|PassportMissing]

# ports/policy.py
Protocol AgentPolicyStore:
    async load() -> Result[PolicyDocument, PolicyStoreFault]

# ports/database.py
Protocol DatabaseGateway:
    async list_schemas() -> Result[…]
    async list_tables(schema) -> …
    async get_table_schema(schema, table) -> …
    async select_rows(schema, table, columns, limit, offset) -> …
    async execute_readonly(sql, max_rows) -> …
    async execute_write(sql, target_table) -> …
    async explain(sql) -> …
    async database_stats() -> …

# ports/sql_analyzer.py
Protocol SqlAnalyzer:
    def analyze(sql: str) -> Result[SqlAnalysis, SqlParseFault]
    # sync OK: CPU-bound parse; no I/O

# ports/events.py
Protocol EventBus:
    def subscribe(handler: Callable[[AgentActionEvent], Awaitable[None]]) -> None
    async emit(event: AgentActionEvent) -> None

# ports/clock.py
Protocol Clock:
    def now_utc() -> datetime
Protocol IdGenerator:
    def new_event_id() -> str      # AgentActionEvent.event_id
    def new_request_id() -> str    # RequestContext / event.meta.request_id
```

`PassportClaims`: `agent_id`, `domain`, `aud`, `exp` — **без** сырого JWT.

---

## 7. Application — commands + services

### 7.1 v1 entry: Invoke Agent Tool

| Артефакт | Путь |
|----------|------|
| Command | `commands/invoke_agent_tool.py` → `InvokeAgentToolCommand` |
| Orchestrator | `services/invoke_agent_tool.py` → `InvokeAgentToolService` |
| Establish ctx | `services/establish_request_context.py` |
| Authorize | `services/authorize_tool.py` |
| Emit | `services/emit_agent_action.py` |
| Context VO | `request_context` / `agent_reply` / `event_outcome` / `execution_plan` |

**Команда (pre-auth, данные):**

```text
InvokeAgentToolCommand:
  bearer_token: str | None
  tool: ToolName
  args: Mapping[str, Any]
  request_id: str | None          # если None → IdGenerator в establish
```

**Сервис-фасад:**  
`InvokeAgentToolService.execute(cmd) -> Result[AgentReply, PreAuthError]`  
Внутри **не** таскает `agent_id`/`clock` россыпью — только через агрегаты §5.1.1.

`PreAuthError` = `PassportMissing | PassportInvalid | AgentNotAllowlisted | PolicyStoreFault`.  
После успешного establish путь **всегда** возвращает `Ok(AgentReply)` (status `ok|error|denied`) после ровно одного emit.

### 7.2 Алгоритм (с RequestContext)

```text
1. established = EstablishRequestContextService.execute(cmd)
   # verify passport → resolve WL → AuthorizedAgent
   # started_at = clock.now_utc()
   # request_id = cmd.request_id or ids.new_request_id()
   Err PreAuth* → return Err          # emit: NO  (RequestContext не создан)
   Ok → ctx: RequestContext

2. authz = AuthorizeToolService.execute(ctx)
   # capability from catalog; if raw-SQL tool → analyzer.analyze(sql) → domain guard(analysis)
   Err CapabilityDenied | StatementClassDenied | SqlParseFault | ToolInputInvalid →
        reply = AgentReply(status="denied", payload=LLM-facing deny body)
        outcome = EventOutcome(reason_code=…, missing_capabilities=…, statement_class=…)
        emit(ctx, status="denied", outcome)
        return Ok(reply)              # LOCKED: post-auth = Ok(AgentReply), not Err

   Ok → plan: ExecutionPlan

3. db_result = run_execution_plan(database, plan)
   Ok  → reply = AgentReply(ok, full rows…); outcome = EventOutcome(rows_count=N)
   Err → reply = AgentReply(error, masked msg…); outcome = EventOutcome(reason_code=database_fault)

4. EmitAgentActionService.emit(ctx, status, outcome)
   # NEVER receives reply.payload
   # duration_ms from ctx.started_at
   # EventOutcome SSOT = domain/auditing (не application/context)

5. return Ok(reply) to presentation  # only path that sees full payload
```

**Сигнатуры:**

```text
EstablishRequestContextService.execute(cmd) -> Result[RequestContext, PreAuthErr]
AuthorizeToolService.execute(ctx) -> Result[ExecutionPlan, AuthzErr]
EmitAgentActionService.emit(ctx, status, outcome: EventOutcome) -> None
# MUST NOT: emit(ctx, reply: AgentReply)  # forbids accidental payload leak
```

Presentation: `AgentReply.payload` → MCP. Subscribers: only `AgentActionEvent` (no rows).

### 7.2.1 Рост application-слоя (обязательно)

Новый use-case = **два файла**, без правки `invoke_agent_tool.py`:

```text
commands/rotate_agent_key.py   + services/rotate_agent_key.py
commands/inspect_agent.py      + services/inspect_agent.py
commands/register_tool.py      + services/register_tool.py
commands/update_policy.py      + services/update_policy.py
```

Новый внешний ресурс = новый файл в `ports/` + adapter в `infrastructure/<area>/`.

### 7.3 Маскирование ошибок БД

Маппинг `asyncpg` exceptions → `DatabaseFault(safe_message)` живёт в **infrastructure**, но **формулировка safe_message** для агента собирается в application (или маленький `ErrorMasker` port), чтобы domain не знал asyncpg.

---

## 8. Событие — контракт (без тела ответа агенту)

### 8.1 Схема (immutable)

```text
AgentActionEvent:
  event_id: str
  ts: datetime
  agent_id: AgentId
  request: { tool: str, args: dict }   # факт вызова; Bearer never
  status: "ok" | "error" | "denied"
  outcome: EventOutcome                # карточка; NEVER rows / LLM body
  duration_ms: int | None
  meta: { domain?, request_id? }
```

**Запрещённые поля (MUST NOT появиться в схеме):** `response`, `payload`, `rows`, `result`, `body`.

Один тип на все исходы authorized-path. Pre-auth → события нет.

### 8.2 EventBus поведение

| Правило | MUST |
|---------|------|
| Подписка | `subscribe` до `serve` / MCP accept |
| Emit | **P5 freeze:** `InProcessEventBus` sequential `await` each handler; swallow sink errors |
| Ошибка sink | log process-level; **не** менять Result tool |
| Ядро | не импортирует `subscribers.*` |

> **Note (P5):** fire-and-forget rewrite is deliberately deferred — sequential await keeps audit ordering simple and ZTA contracts stable.

### 8.3 Subscribers (примеры)

| Sink | Регистрация | Поведение | Кто поставляет |
|------|-------------|-----------|----------------|
| `ConsoleSink` | bootstrap if `ENABLE_CONSOLE_EVENT_SINK=1` (default on) | JSON-lines stdout **карточек событий** | **этот репозиторий** — демо ивентов |
| Custom (SIEM / DB / свой transport) | user code `bus.subscribe(fn)` | куда угодно интегратору | **форк / пользователь** — **не** maintainers |

В этом пакете **нет** WebhookSink и **нет** env `WEBHOOK_URL` — outbound webhook-системы не ship’им.

Sink **не** является process logger. Ошибка sink → `observability.log` ERROR + `mcp_sink_error_total`; Result tool не меняется.

### 8.4 Process observability vs EventBus (жёсткое разделение)

| | Process obs (A/B) | Agent event + sink (C) |
|--|-------------------|------------------------|
| API | `bootstrap.observability` | `EmitAgentActionService` → `EventBus` |
| Pre-auth fail | **да** (log + metric) | **нет** события |
| Post-WL deny/ok/error | да (ops) | да (audit card) |
| Может влиять на UC Result | **нет** | **нет** (sink swallow) |
| Удаление ConsoleSink | не влияет | пропадает JSONL audit |
| HTTP export | нет (`/mcp` only) | нет |

```text
                    ┌──────────────────────────────────┐
  layers ──────────►│ bootstrap.observability (SSOT)   │──► JSONL (+ metrics.summary)
  (app/infra/pres.) │  log · metrics · context · redact│
                    └──────────────────────────────────┘

  Invoke ──emit──► EventBus ──► ConsoleSink / Webhook  (optional, one-way)
                     ▲
                     └── только AgentActionEvent; никогда AgentReply.payload
```

---

## 9. Infrastructure

### 9.1 `LimePassportVerifier`

- Вход: raw Bearer token (с/без префикса; нормализация в адаптере).  
- Реализация: обёртка над `lime_mcp_server.TokenVerifier` (JWKS cache, RS256, `aud`, domain pin).  
- Hot path: **нет** обязательного HTTP на каждый call после прогрева JWKS (SDK cache).  
- Ошибки → `PassportInvalid` / `PassportMissing` (Result, не исключения наружу из port).  
- Unit-тесты инжектят fake `TokenVerifier` (без сети / lime.pics).

### 9.2 `JsonAgentPolicyStore` — cache + TTL/mtime + atomic replace

- Читает `AGENTS_POLICY_PATH`, валидирует через `PolicyDocument.from_mapping`.  
- **In-memory cache** текущего снимка (immutable `_Snapshot`).  
- **Reload без рестарта (v1 MUST):** lazy проверка при `current()` под `asyncio.Lock`; если `(now - checked_at) >= TTL` → `stat` mtime → при изменении load → validate → **atomic replace**.  
- **Soft-keep:** при ошибке reload, если уже был хороший снимок → вернуть старый `Ok` и обновить `checked_at` (не `PolicyStoreFault`). Первый load fail → `PolicyStoreFault`.  
- `EstablishRequestContext` держит `PolicySnapshot` на момент вызова — mid-flight switch не требуется.
### 9.3 `AsyncpgDatabaseGateway` — session guards + single-statement

Gateway **не** заменяет AST: class уже проверен в `Authorize_tool`.  
Gateway добивает envelope и anti-Datadog:

- **Один** statement на execute; драйвер/путь, который **не** принимает `a; b;` одной multi-query строкой (extended/prepared).  
- Read tools / readonly SQL: `BEGIN` + `SET LOCAL transaction_read_only = on` (ловит modifying CTE, если AST багнут).  
- Агент **не** шлёт `BEGIN`/`COMMIT` — txn владеет gateway.

`READ ONLY` txn **недостаточен** против DoS (`pg_sleep`, recursive CTE).  
**MUST** на **каждом** tool DB call (внутри txn, `SET LOCAL`):

| Guard | Env / Settings | Default (v1) | Зачем |
|-------|----------------|--------------|--------|
| `statement_timeout` | `PG_STATEMENT_TIMEOUT` | `5s` | режет sleep / долгий SQL |
| `lock_timeout` | `PG_LOCK_TIMEOUT` | `2s` | не висеть на блокировках |
| `idle_in_transaction_timeout` | `PG_IDLE_IN_TRANSACTION_TIMEOUT` | `10s` | брошенные txn |
| `max_rows` | из `PolicyDocument.max_rows` + clamp | policy | объём строк |
| `max_result_bytes` | `PG_MAX_RESULT_BYTES` | `1_048_576` (1 MiB) | потолок сериализованного результата |

Порядок на вызов:

```text
BEGIN [READ ONLY if readonly tool]
SET LOCAL statement_timeout = …
SET LOCAL lock_timeout = …
SET LOCAL idle_in_transaction_timeout = …
-- execute
-- enforce max_rows / max_result_bytes on read path
COMMIT/ROLLBACK
```

Прочее:

- Pool из `POSTGRES_URL`.  
- `select_rows`: identifier allowlist + bound params.  
- `execute_readonly_query`: READ ONLY + class=`READ` + guards.  
- `execute_write_query`: class=`DML` only + guards; **не** DDL.  
- **MUST NOT:** string-concat SQL.  
- SQL class — до gateway; timeout/bytes — **обязанность gateway** (SSOT enforcement).  
- Превышение timeout/bytes → `DatabaseFault` (masked) → `AgentReply` error + `EventOutcome(reason_code=…)` без payload.

### 9.4 `InProcessEventBus`

- `list[Handler]`; `emit` создаёт `asyncio.create_task` на каждого (или очередь).  
- Для тестов: `RecordingEventBus` собирает events в list.

### 9.5 Time / Id

- `SystemClock`, `Uuid4IdGenerator` — prod.  
- Tests: `FixedClock`, `SequenceIds`.

### 9.6 Process observability — SSOT (Prime B03 / OWASP A09) · PRD §8 · ADR-003

**Роль:** публичный контракт observability **процесса** MCP-сервера (open-source reference).  
Не audit личности агента. Не subscriber. Не HTTP `/metrics`.

#### 9.6.1 Пакет

```text
bootstrap/observability/
  __init__.py       # re-export public API only
  schema.py         # SCHEMA_ID = "lime.mcp.process_log.v1"
  redaction.py      # FORBIDDEN_KEYS + sanitize_fields()
  context.py        # bind_context / clear_context / get_bound (contextvars)
  logging.py        # JsonLineRenderer | ConsoleRenderer; ProcessLogHandler
  metrics.py        # ProcessMetrics (counters + fixed histograms)
  configure.py      # configure_observability(...)
```

**Public API (единственный импорт для слоёв):**

```text
from lime_ref_postgres_mcp.bootstrap.observability import (
    configure_observability,
    get_logger,
    log,
    metrics,          # ProcessMetrics singleton for process
    bind_context,
    clear_context,
)

configure_observability(*, level, format="json", stream=stderr, metrics_enabled=True) -> None
    # idempotent; MUST from serve / bootstrap only

get_logger(component: str) -> LoggerProxy
    # component ∈ {serve, identity, policy, establish, authorize, db, events, mcp, metrics}

log(component|logger, event: str, *, level="INFO", **fields) -> None
    # merges bound context; applies redaction; emits ONE schema v1 record
    # auto-skips None; non-scalars → "<redacted>" or type name

bind_context(**fields) / clear_context()
    # request_id, agent_id, trace_id, parent_span_id

metrics.inc(name, **labels) / metrics.observe_ms(name, value, **labels)
metrics.snapshot() -> Mapping   # for tests / embedders
```

**Default format = JSON Lines** (open-source / aggregators).  
`format=console` — тот же schema, human renderer.

#### 9.6.2 Record shape (MUST)

```json
{
  "schema": "lime.mcp.process_log.v1",
  "ts": "2026-08-04T12:00:00.000Z",
  "level": "INFO",
  "component": "mcp",
  "event": "tools.call.done",
  "request_id": "…",
  "tool": "select_rows",
  "outcome": "ok",
  "duration_ms": 18
}
```

Clock for `ts` — injected/`time.time` only in observability infra (не domain).

#### 9.6.3 Call matrix (contributor law)

| Компонент | component= | Events | Metrics |
|-----------|------------|--------|---------|
| serve / CLI | `serve` | `serve.start/stop`, `config.error` | — |
| lifespan | `serve` | `jwks.warmup`, `pool.open/close`, `metrics.summary` | warmup/pool; summary dump |
| `LimePassportVerifier` | `identity` | `verify.ok/fail`, `jwks.warmup` | — |
| `JsonAgentPolicyStore` | `policy` | `policy.load/reload/soft_keep` | — |
| `EstablishRequestContextService` | `establish` | `preauth.fail`, `context.ok` | `mcp_preauth_fail_total` |
| `AuthorizeToolService` | `authorize` | `authorize.allow/deny` | `mcp_authorize_deny_total` |
| `AsyncpgDatabaseGateway` | `db` | `db.op`, pool events | `mcp_db_op_*` |
| `EmitAgentActionService` | `events` | `emit` | `mcp_emit_total` |
| `InProcessEventBus` | `events` | `sink.error` | `mcp_sink_error_total` |
| MCP handlers | `mcp` | `tools.call.start/done`, `tools.list`, `unknown_tool` | `mcp_tools_call_*` |

**MUST NOT** звать facade из `domain/**`.  
**MUST:** presentation на входе call — `bind_context(request_id=…, trace_id?=…)` и `clear_context()` в `finally`.  
**MUST:** на `Err` — `invariant_id`/`code` + safe ids (A10).

#### 9.6.4 Correlation

1. Presentation/Establish создаёт `request_id` (Id port).  
2. `bind_context(request_id=…)`.  
3. После verify — `bind_context(agent_id=…)`.  
4. Optional: parse `traceparent` → `trace_id`, `parent_span_id` (no OTel SDK required).  
5. Тот же `request_id` → `AgentActionEvent.meta.request_id`.  
6. `clear_context()` в `finally` (no leak across concurrent tasks).

#### 9.6.5 Redaction

Deny-list (case-insensitive) enforced in `redaction.py` before render — см. ADR-003.  
INFO: no SQL values; DEBUG: `sql_preview≤80` **or** `args_keys` only.

#### 9.6.6 Metrics implementation notes

- Thread/async-safe atomics (`threading.Lock` or `collections` under lock).  
- Histograms: fixed buckets from PRD §8.5 (no prometheus_client dep in v1).
- `LIME_MCP_METRICS=0` → no-op registry (tests that ignore metrics).  
- Shutdown: `log("metrics", "metrics.summary", **snapshot_flat)`.

#### 9.6.7 Settings

| Env | Default | Settings field → |
|-----|---------|------------------|
| `LIME_MCP_LOG_LEVEL` | `INFO` | `log_level` |
| `LIME_MCP_LOG_FORMAT` | `json` | `log_format` (`json`\|`console`) |
| `LIME_MCP_LOG_STREAM` | `stderr` | `log_stream` |
| `LIME_MCP_METRICS` | `1` | `metrics_enabled` |

Не путать с `ENABLE_CONSOLE_EVENT_SINK`.

#### 9.6.8 Тесты

| Тест | Assert |
|------|--------|
| `test_observability_schema.py` | every record has schema/ts/level/component/event |
| `test_observability_redaction.py` | forbidden keys dropped/redacted; JWT-like values never appear |
| `test_observability_configure.py` | idempotent configure; format json\|console |
| `test_observability_context.py` | bind/clear; no cross-task leak (async) |
| `test_observability_metrics.py` | inc/observe → snapshot labels |
| establish preauth | caplog/`log` capture `preauth.fail` + metric |
| invoke deny | authorize.deny + emit; RecordingEventBus has event |
| ConsoleSink off | process JSONL + metrics still work |
| route-matrix | still **no** `/health` `/metrics` |

`pii-log-scan` / `no-secrets` LIVE — facade не тащит секреты.

---

## 10. Presentation — MCP

Нормативная граница auth: **[ADR-001](./ADR-001-mcp-authentication-boundary.md)**.  
Нормативная граница observability: **[ADR-003](./ADR-003-process-observability.md)**.

### 10.1 Транспорт

- Remote HTTP MCP (streamable HTTP / SSE — по official SDK).  
- Passport: **только** `Authorization: Bearer` → `extract_bearer` → `InvokeAgentToolCommand`.  
- Stdio / session-only auth: **out of scope v1** (см. ADR-001).  
- Unit UC-тесты **без** HTTP: command inject + Fake ports.

### 10.2 Thin handlers

Каждый tool в `presentation/mcp/handlers/*`:

```text
async def list_schemas(invoke, bearer_token, args) -> CallToolResult:
    return await invoke_tool(invoke, ToolName.LIST_SCHEMAS, bearer_token, {})
```

Server `on_call_tool` supplies `bearer_token=extract_bearer(ctx.request)` into
`InvokeAgentToolCommand(bearer_token=…)`.

**Лимит логики в handler:** < 15 строк (Prime handler-purity).  
Нет SQL, нет JWKS, нет `print` агентских логов.

### 10.3 `extract_bearer`

- Читает header case-insensitive (`Request.headers` first — Request is a Mapping).  
- `None` / empty → command с `bearer_token=None` → `PassportMissing`.

### 10.4 MCP «API» surface (tools)

Внешний контракт агента = 8 tools из PRD §8 (сигнатуры без паспорта).  
Дополнительно **не** HTTP REST API в v1.

### 10.5 Подписка на события (программный API пакета)

```text
# для разработчика, встраивающего пакет
runtime = build_runtime(settings)
runtime.event_bus.subscribe(my_handler)
await runtime.run_mcp()
```

Это и есть «взять записку со стола»: `subscribe` на `EventBus`.

---

## 11. Потоки данных

### 11.1 Happy path

```text
MCP Client
  → Bearer + tools/call select_rows
    → presentation.auth.extract_bearer
    → InvokeAgentToolService
         → PassportVerifier.verify → AgentId
         → PolicyStore → AuthorizedAgent(permissions⊇READ_DATA)
         → DatabaseGateway.select_rows
         → EventBus.emit(status=ok, outcome={rows_count})
    ← ToolOutcome rows
  ← MCP tool result
         → (async) ConsoleSink / custom
```

### 11.2 Нет в whitelist

```text
verify OK → resolve FAIL AgentNotAllowlisted
  → Err to presentation → MCP error
  → EventBus.emit НЕ вызывается
```

### 11.3 Нет WRITE_DATA, вызвали execute_write_query

```text
AuthorizedAgent → CapabilityDenied(WRITE_DATA)
  → emit(denied, outcome.reason_code=capability_denied)  # без текста/rows
  → MCP error (полный deny body только агенту)
```

### 11.4 Есть WRITE_DATA, SQL = DROP TABLE

```text
AuthorizedAgent → classify DDL → StatementClassDenied
  → emit(denied, outcome.statement_class=DDL)
  → MCP error агенту
```

### 11.4 Sequence (упрощённо)

```mermaid
sequenceDiagram
  participant C as MCP Client
  participant P as Presentation
  participant A as InvokeAgentToolService
  participant V as PassportVerifier
  participant S as PolicyStore
  participant D as DatabaseGateway
  participant E as EventBus
  participant X as Subscriber

  C->>P: tools/call + Bearer
  P->>A: InvokeAgentToolCommand
  A->>V: verify
  alt passport/whitelist fail
    V-->>A: Err
    A-->>P: Err (no emit)
    P-->>C: error
  else authorized
    A->>S: resolve permissions
    alt capability or SQL class deny
      A->>E: emit(denied)
      A-->>P: Err
      P-->>C: error
    else allowed
      A->>D: execute
      D-->>A: rows|fault
      A->>E: emit(ok|error)
      A-->>P: Result
      P-->>C: tool result
      E-->>X: event (async)
    end
  end
```

---

## 12. Конфигурация и Settings

Предполагается обычный `.env` / env хоста (не git). Доступ MCP-процесса к Postgres — **одним** стандартным URL, логин и пароль внутри строки:

```env
# личность агентов (LIME)
LIME_EXPECTED_DOMAIN=your-corporate-domain.com
LIME_JWKS_URL=https://lime.pics/.well-known/jwks.json
AGENTS_POLICY_PATH=./config/agents.json
POLICY_RELOAD_TTL_SECONDS=60

# ресурс за дверью (учётка сервиса MCP → Postgres)
POSTGRES_URL=postgresql://user:password@host:5432/dbname
PG_STATEMENT_TIMEOUT=5s
PG_LOCK_TIMEOUT=2s
PG_IDLE_IN_TRANSACTION_TIMEOUT=10s
PG_MAX_RESULT_BYTES=1048576

# опционально: демо audit агента (канал C) — ConsoleSink only
# ENABLE_CONSOLE_EVENT_SINK=1

# process observability (каналы A/B — ADR-003)
LIME_MCP_LOG_LEVEL=INFO
LIME_MCP_LOG_FORMAT=json
# LIME_MCP_LOG_STREAM=stderr
# LIME_MCP_METRICS=1
```

Пример `config/agents.json`:

```json
{
  "max_rows": 100,
  "agents": {
    "agent_abc123": {
      "permissions": ["READ_SCHEMA", "READ_DATA"]
    },
    "agent_fin_5678": {
      "permissions": ["READ_SCHEMA", "READ_DATA", "WRITE_DATA"]
    }
  }
}
```

| Env | Куда | Слой |
|-----|------|------|
| `POSTGRES_URL` | pool | infra |
| `PG_STATEMENT_TIMEOUT` / `PG_LOCK_TIMEOUT` / `PG_IDLE_IN_TRANSACTION_TIMEOUT` | `SET LOCAL` per call | infra gateway |
| `PG_MAX_RESULT_BYTES` | truncate/fail read path | infra gateway |
| `LIME_*` / `AGENTS_POLICY_PATH` | verifier + policy | infra |
| `POLICY_RELOAD_TTL_SECONDS` | policy cache refresh | infra |
| `ENABLE_CONSOLE_EVENT_SINK` | bootstrap → ConsoleSink (демо) | subscribers |
| `LIME_MCP_LOG_*` / `LIME_MCP_METRICS` | `configure_observability` | bootstrap/observability |

- Канон БД-доступа: один `POSTGRES_URL` (user/password в URL).  
- Credentials **сервиса** ≠ passport агента.  
- `Settings` frozen; Domain не читает env.

---

## 13. Классы / модули (сводка ответственности)

| Символ | Путь | Ответственность |
|--------|------|-----------------|
| `AgentId` | `domain/agent/` | id |
| `ToolCapability`, `PolicyDocument` | `domain/access/` | permissions |
| `SqlAnalysis`, `SqlGuardDecision` | `domain/sql/` | класс/флаги + pure allow/deny |
| `tool_catalog` | `domain/catalog/` | tool → capability |
| `AgentActionEvent` | `domain/auditing/` | форма события |
| `Result`, `DomainError` | `domain/common/` | исходы |
| `PassportVerifier` | `application/ports/identity.py` | port |
| `AgentPolicyStore` | `application/ports/policy.py` | port |
| `DatabaseGateway` | `application/ports/database.py` | port |
| `SqlAnalyzer` | `application/ports/sql_analyzer.py` | port |
| `PglastSqlAnalyzer` | `infrastructure/sql/` | AST walk (libpg_query) |
| `EventBus` | `application/ports/events.py` | port |
| `InvokeAgentToolCommand` | `application/commands/invoke_agent_tool.py` | pre-auth вход |
| `RequestContext` | `application/context/request_context.py` | post-WL correlation |
| `AgentReply` | `application/context/agent_reply.py` | полный ответ → MCP |
| `EventOutcome` | `domain/auditing/event_outcome.py` | карточка → event |
| `ExecutionPlan` | `application/context/execution_plan.py` | gateway call |
| `InvokeAgentToolService` | `application/services/invoke_agent_tool.py` | фасад UC |
| `EstablishRequestContextService` | `application/services/establish_request_context.py` | passport+WL→ctx |
| `AuthorizeToolService` | `application/services/authorize_tool.py` | caps+SQL→plan |
| `EmitAgentActionService` | `application/services/emit_agent_action.py` | ctx+EventOutcome→event |
| Adapters | `infrastructure/*/` | JWKS / JSON / asyncpg / bus |
| `observability` | `bootstrap/observability/` | SSOT process log+metrics+correlation (ADR-003) |
| MCP handlers | `presentation/mcp/handlers/` | thin transport |
| `ConsoleSink` / sinks | `subscribers/` | optional one-way audit consumers |
| `build_runtime()` | `bootstrap/container.py` | DI |

**Anti-god:** нет `PostgresMcpServer`; нет одного `invoke_tool.py` на все будущие UC.

---

## 14. Безопасность (Prime A02 / A16 / A18 / A29)

### 14.1 ZTA matrix (обязательные сценарии тестов)

| # | Scenario | Event? |
|---|----------|--------|
| Z1 | No Bearer / bad JWT | нет |
| Z2 | Not in whitelist | нет |
| Z3 | WL + только READ_* → `execute_write_query` | да, `capability_denied` |
| Z4 | WL + WRITE_DATA → `DROP` via write tool | да, `statement_class_denied` |
| Z5 | WL + READ_DATA → `select_rows` ok | да, `ok` |
| Z6 | WL + WRITE_DATA → top-level `INSERT` ok | да, `ok` |
| Z7 | WL + без ADMIN → `get_database_stats` | да, `capability_denied` |
| Z8 | WL + READ_DATA → `WITH (DELETE…) SELECT` on readonly | да, `statement_class_denied` |
| Z9 | WL + READ_DATA → `COMMIT; DROP…` multi-stmt | да, denied/`UNKNOWN` |
| Z10 | WL + WRITE_DATA → modifying-CTE + outer SELECT on write | да, denied (не top-level DML) |

Каждая клетка → `tests/contract/test_zta_matrix.py`.  
AST payloads → `tests/unit/infrastructure/sql/test_adversarial_payloads.py`.

### 14.2 Threat Model mini (A16)

| Threat | Mitigation |
|--------|------------|
| Украденный passport | short-lived JWT + domain pin + WL |
| Prompt injection → destructive SQL | capabilities; AST walk; WRITE≠DDL; single-stmt; READ ONLY txn; RO role |
| CTE-write под видом SELECT | AST → DML; readonly deny; READ ONLY txn belt |
| Multi-stmt escape (`COMMIT; DROP`) | analyzer `statement_count`; no multi-query execute |
| DoS через SQL tools (`pg_sleep`, heavy CTE) | `SET LOCAL statement_timeout` / `lock_timeout` / idle; `max_rows`; `max_result_bytes` |
| Утечка схемы ошибок | DatabaseFault masking для AgentReply |
| Утечка данных через audit/webhook | event без payload; только EventOutcome |
| Скомпрометированный агент в WL | policy TTL/mtime reload → atomic replace; без restart |
| Passport в логах | redaction; never in event.args |
| Подмена tool args → другой agent | agent_id только из verify |

### 14.3 Secrets

- `POSTGRES_URL` только env; не в git.  
- JWKS public; agent master key **не** живёт в этом пакете (выдача паспортов = lime.pics / agent SDK).

---

## 15. Тестирование (Prime A12 / A24 / A25)

| Слой | Что | Как |
|------|-----|-----|
| Domain | policy, guard(SqlAnalysis fixtures), event immutability | pure unit |
| Infra SQL | `PglastSqlAnalyzer` + adversarial suite | unit (без БД) |
| Application | полный pipeline с Fake ports (FakeSqlAnalyzer) | unit; RecordingEventBus |
| Presentation | bearer extract, error_map, MCP dispatch | unit |
| Process observability | schema/redaction/metrics/context; wire establish/invoke | unit |
| Contract | ZTA matrix × tools | contract |
| Infra PG | READ ONLY envelope, timeouts | integration when docker |
| Subscribers | ConsoleSink only | unit |

**Coverage:** greenfield package → `runtime_scope = src/lime_ref_postgres_mcp` → 100% line+branch на PRIME.  
**Determinism:** no `datetime.now` / `uuid4` в domain/application — только Clock/Id ports.

---

## 16. Composition root — порядок старта

```text
1. Settings.from_env()
2. configure_observability(level, format, stream, metrics_enabled)  # ADR-003 SSOT
3. clock, ids = System*, Uuid*
4. verifier = LimePassportVerifier(settings)
5. policy_store = JsonAgentPolicyStore(path)
6. sql_analyzer = PglastSqlAnalyzer()
7. db = create_database(settings)   # lazy pool — open() in serve lifespan
8. bus = InProcessEventBus()
9. if console_enabled: bus.subscribe(ConsoleSink())      # shipped event DEMO only
10. # no WebhookSink — integrators bus.subscribe themselves
11. invoke = InvokeAgentToolService(establish, authorize, emit, db)
12. mcp = build_mcp_server(runtime)  # lifespan: warmup → db.open → serve → close
13. uvicorn Streamable HTTP /mcp
14. on shutdown: metrics.summary log → clear handlers
```

Единственное место concrete classes. Новые UC → новые `Service(...)` в том же `container.py`, без правки `InvokeAgentToolService`.  
`configure_observability` — **до** warmup; слои пишут только через facade.

---

## 17. Нефункциональные требования

| Тема | v1 target |
|------|-----------|
| Latency verify | JWKS cache; no lime.pics RTT per tool after warm |
| Emit | async; p99 tool path не ждёт сторонний sink |
| Pool | asyncpg pool size из settings (default conservative) |
| Observability process | ADR-003: JSONL schema v1 + metrics + correlation; `/mcp` only; **не** agent audit |
| Agent audit console | shipped `ConsoleSink` demo on EventBus only (one-way) |
| SemVer | package 0.1.0; process log schema `v1` (bump via ADR); event schema version later if break |

---

## 18. Этапы реализации (design-first order A07)

| Phase | Deliverable | Gate |
|-------|-------------|------|
| P0 | TDD + PRD freeze (этот документ) | review |
| **Day0** | Package skeleton: hatchling/`uv.lock`, layers, `Result`/`DomainError`, frozen `Settings`, `build_runtime`→`Runtime{settings,clock,ids}`, Clock/Id ports+adapters, import-law tests | **done** — ruff+mypy+pytest 100% cov |
| **Day0.5** | Package-local AGENT-5 `prime_check` (`scripts/prime_check/`, AST gates, ADR-002 skips, nested `.github`) | **done** — `uv run python -m scripts.prime_check` exit 0 |
| **P1** | domain: policy + capabilities + SqlAnalysis/guard (fixtures; no pglast) | **done** — unit + `prime_check` exit 0 / 100% cov |
| **P1b** | `PglastSqlAnalyzer` + adversarial suite | **done** — unit + `injection-fuzz` LIVE / 100% cov |
| **P2** | `InvokeAgentToolService` + Fake ports + EventBus + ZTA Z1–Z10 | **done** — unit + `zta-matrix-gate` LIVE / 100% cov |
| **P3** | JsonPolicy + LimeVerifier | **done** — unit lite + SDK wrap + soft-keep / 100% cov |
| **P4** | AsyncpgGateway (READ ONLY + single-stmt + timeouts) + Testcontainers | **done** — unit 100% + LIVE `pytest-integration` |
| **P5** | MCP presentation + bootstrap + ConsoleSink | **done** — unit 100% + LIVE contract/e2e/route-matrix |
| **P5.1** | Process observability (`bootstrap/observability`) + wire + tests | **done** — PRD §8 / TDD §9.6 / ADR-003 shipped |
| **P6** | keep CI green as package grows | **done** — SBOM LIVE + hardened `.github/workflows/prime_check.yml` |

**Cancelled / never ours:** former «P7 WebhookSink» — out of scope for maintainers; community/fork extension only.

**Mandated order:** Day0 → Day0.5 → P1 → P1b → P2 → P3 → P4 → P5 → P5.1. Do **not** start P5 without P4 green.

---

## 19. Явные non-goals архитектуры v1

- OAuth 2.1 browser dance внутри пакета (passport выдан LIME; PRM-совместимость — отдельный трек).  
- Stdio / session-only auth без Bearer на call (см. ADR-001).  
- Per-table ACL / schema allowlist в AST.  
- Modifying-CTE на write-tool (v1 deny).  
- SQL cost / EXPLAIN gates.  
- Text/regex classifier как SSOT.  
- Push/pubsub инвалидации policy (есть TTL/mtime pull).  
- Хранение аудита внутри процесса.  
- Смешение ConsoleSink / process observability в один канал.  
- Observability вызовы из `domain/**`.  
- REST `/health` или `/metrics` в v1 (поверхность только `/mcp`).  
- **WebhookSink / outbound audit HTTP** (интегратор пишет сам; `ssrf-gate` остаётся SKIPPED).  
- Эксплуатация пакета как прод LIME (только GitHub showcase).  
- Bypass «dev without passport».  
- Бизнес-логика в MCP handler’ах.

---

## 20. Соответствие PRD ↔ TDD (чеклист)

| PRD / review | TDD / ADR |
|--------------|-----------|
| Bearer passport | `extract_bearer` + `PassportVerifier` + **ADR-001** |
| Capabilities (не mode) | `ToolCapability` + permissions |
| SQL AST (не text) | §5.5 `PglastSqlAnalyzer` + `SqlGuardDecision` |
| CTE-DELETE ≠ READ | adversarial + Z8 |
| WRITE ≠ DDL; write = top-level DML | guard rules |
| Layers: AST + single-stmt + READ ONLY + role | §5.5 / §9.3 / deploy |
| Session timeouts / max bytes | §9.3 `SET LOCAL` + Settings |
| Policy reload без restart | §9.2 TTL/mtime + atomic replace |
| Event без тела ответа агенту | `EventOutcome` |
| ConsoleSink демо снаружи (one-way) | `subscribers/console_sink.py` · §8.3–8.4 |
| Custom sinks (webhook…) | integrator `bus.subscribe` — **not** shipped |
| Process observability (B03 triad) | §9.6 · PRD §8 · **ADR-003** |
| Domain без obs I/O | §1 / §9.6.3 |
| No `/metrics` HTTP v1 | ADR-003 · route-matrix |

---

## 21. Одной формулой

```text
Presentation
  → bind_context(request_id, trace?)
  → observability.log (tools.call.*) + metrics
  → InvokeAgentToolService(cmd)
       → EstablishRequestContext → RequestContext | Err(no emit)
            + log (preauth.* | context.ok) + metrics
       → AuthorizeTool → plan | (AgentReply to MCP + EventOutcome to emit)
            + log (authorize.*) + metrics
       → DB → AgentReply(full) + EventOutcome(card)
            + log (db.op) + metrics
       → Emit(ctx, status, outcome)   # never payload
            + log (emit) + metrics
  → clear_context()
  → MCP ← AgentReply.payload
  → subscribers ← event without rows   # optional overlay; one-way only
```

**Формула разделения:**

```text
observability.log/metrics = «что делает сервер»   (внутри, SSOT, всегда, schema v1)
AgentActionEvent          = «что сделал агент»    (после WL, audit)
ConsoleSink               = «демо карточки»       (снаружи, optional, delete-safe)
custom sink               = «логи куда-то себе»   (форк/интегратор, не maintainers)
```

**Empire:** явные ошибки, порты, ZTA matrix, без I/O в core.  
**Skin:** Python package + MCP handlers + asyncpg.  
**Product:** open-source showcase паспорта LIME; дверь + capabilities; не прод-сервис LIME.
