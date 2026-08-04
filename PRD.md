# PRD — Reference MCP: агент с паспортом LIME → PostgreSQL

**Что это:** **open-source showcase** технологии личности агента LIME: дверь к Postgres по MCP  
**Статус:** showcase sealed through **P6** (CI green + SBOM) — reference / публичный демо-код (не продуктовый сервис LIME)  
**Для кого:** разработчики и команды, которые смотрят, как устроен паспорт LIME на живом ресурсе; форки и интеграторы  
**Зачем документ:** показать полный путь «паспорт → кто допущен → действие → событие» на живом ресурсе (БД)  
**Как используем мы:** **не используем в проде LIME.** Пакет лежит на GitHub как эталон. Эксплуатация, webhook’и и «логи куда-то себе» — на стороне тех, кто взял сервер себе.

---

## 1. Что мы хотим сделать

Агент приходит к ресурсу **как личность** (паспорт LIME), а не как аноним с общим ключом от базы.  
Postgres здесь — конкретная дверь: MCP-инструменты к БД за тем же пропуском.

1. На входе — паспорт в `Authorization: Bearer <passport>`; без него дверь закрыта.
2. Дальше — только агенты из **whitelist**; у каждого набор **permissions** (capabilities), плюс общий `max_rows`.
3. Когда разрешённый агент опознан — по итогам действия появляется **событие** одного формата: кто, что запросил, чем кончилось (`ok`/`error`/`denied`). **Тело ответа агенту в событие не кладём.**
4. Паспорт не прошёл или агента нет в whitelist — отказ, **события нет** (личности «своего» не было).
5. Ядро только порождает событие. **В этом репозитории** единственный поставленный пример consumer’а — `ConsoleSink` (консоль карточек действий агента): показывает, как устроена система ивентов. Любой другой sink (webhook, SIEM, своя БД) — **не наш scope**; его пишет тот, кто форкает/внедряет сервер у себя (`bus.subscribe(...)`). Sink **только читает** событие и **ничего не пишет обратно** в pipeline.
6. Отдельно от аудита агента — **технические логи процесса** (process observability): жизнь MCP-сервера. Это **не** §7 и не ConsoleSink. См. **§8** · [ADR-003](./ADR-003-process-observability.md).

Коротко по шагам:

```
паспорт агента → whitelist?
        │ нет / паспорт битый → отказ, БЕЗ события
        │                      (+ строка в техлоге процесса)
        ▼ да
permissions (capabilities) → инструмент / класс SQL → Postgres → событие итога
                                                              ↓
                         ConsoleSink (демо в репо) / свой sink у интегратора
                                        ▲ только consume, без обратной связи в ядро
```

---

## 2. Какая боль сейчас

Агенты ходят в инфру без имени — в том числе в БД через типичные MCP:

| Проблема | Что из этого следует |
|----------|----------------------|
| Один общий секрет к ресурсу (`POSTGRES_URL` и т.п.) | Все роботы безлики; взлом одного = радиус на весь ресурс |
| Нет стабильного `agent_id` на входе | Нельзя сказать, *кто* что сделал |
| Логи ресурса без личности агента | Нет цепочки «агент → действие → ответ» |
| Аудит некуда «подцепить» | Свою систему действий агентов не собрать без переписывания шлюза |

---

## 3. Как здесь устроена дверь

Тот же паспорт LIME, что и для других ресурсов агента; за дверью — Postgres по MCP:

- **Пропуск:** JWT паспорта (`agent_id` в `sub`), проверка через локальный JWKS (после кэша без round-trip к lime.pics на каждый tool call).
- **Кого пускаем:** deny-by-default whitelist + permissions (`READ_SCHEMA` / `READ_DATA` / `WRITE_DATA` / `DDL` / `ADMIN`).
- **След:** событие только когда разрешённый агент уже опознан; в репо — демо `ConsoleSink`; свои sinks — у интегратора.

Открытый **showcase** на GitHub: агент с паспортом с lime.pics проходит сюда так же, как к любому ресурсу, который проверяет LIME. Maintainers не гоняют это как свой прод.

---

## 4. Жизненный цикл одного вызова

Порядок жёсткий. Сначала личность агента, потом ресурс. Ответ агенту не ждёт чужой мониторинг. Событие — только после опознания разрешённого агента.

```
[Агент с паспортом]  -- Bearer + tool call -->  [дверь к Postgres / MCP]
         │
         ▼
   1. Личность (JWT / JWKS)
         │
         ├── fail → отказ агенту → СОБЫТИЯ НЕТ → конец
         ▼ ok → agent_id
   2. Whitelist
         │
         ├── нет в списке → отказ агенту → СОБЫТИЯ НЕТ → конец
         ▼ да (разрешённый агент опознан)
   3. permissions агента (capabilities)
         │
         ├── нет нужного permission / SQL-класс не покрыт → отказ + событие (denied)
         ▼ ok
   4. Postgres
         │
         ▼
   5. Событие итога (ok | error) → ответ агенту

   (снаружи ядра) сторонний код может читать событие — не функционал ивентов
```

**Когда события нет:** не удалось идентифицировать разрешённого агента (сломан/нет паспорта, verify fail, `agent_id` ∉ whitelist).  
**Когда событие есть:** агент уже в whitelist; дальше отказ по capability / классу SQL, ошибка БД или успех — одна схема события. Консоль/webhook в ядро не входят (`ConsoleSink` — демо в репо; остальное — у интегратора).

---

## 5. Паспорт на входе (Bearer)

Агент предъявляет паспорт в заголовке:

```http
Authorization: Bearer <lime_passport_jwt>
```

Дальше:

- Проверка: подпись RS256 / JWKS с lime.pics (кэш в процессе).
- Из паспорта берём `agent_id` (`sub`) — по нему права и журнал.
- Смотрим также: `aud`, domain pin, `exp`.
- Нет заголовка / битый / просрочен → tool не выполняется, отказ агенту, **событие не создаётся**.

Ориентир по стеку: Python 3.10+, официальный SDK `mcp`, драйвер `asyncpg`, проверка как в LIME MCP server SDK / те же правила JWKS, что на lime.pics.

---

## 6. Модель доступа (v1) — capabilities, не read/write

Грубый `mode: read|write` **не используем**: «писать» ≠ одно право.  
`INSERT`/`UPDATE`/`DELETE` и `DROP`/`ALTER`/`CREATE` — разный радиус поражения.

Файл: `config/agents.json`.

### 6.1 Рычаги v1

1. **Whitelist** — ключи в `agents`. Нет в списке → отказ, **события нет**.  
2. **`permissions`** — набор `ToolCapability` у агента (см. ниже).  
3. **`max_rows`** глобально — потолок строк / LIMIT на readonly SQL.

### 6.2 Capabilities (`ToolCapability`)

| Capability | Смысл | Примеры операций |
|------------|--------|------------------|
| `READ_SCHEMA` | Смотреть структуру | schemas / tables / columns |
| `READ_DATA` | Читать данные | SELECT, readonly SQL, EXPLAIN |
| `WRITE_DATA` | Менять **данные** (DML) | INSERT, UPDATE, DELETE |
| `DDL` | Менять **схему** | CREATE, ALTER, DROP, TRUNCATE, … |
| `ADMIN` | Сервисная/инфра информация | database stats и подобное |

**Критично:** `WRITE_DATA` **не** включает DDL. Агент с `WRITE_DATA` без `DDL` не должен иметь путь «удалить таблицу».

### 6.3 Какой tool какое permission требует

| Tool | Нужен capability |
|------|------------------|
| `list_schemas` | `READ_SCHEMA` |
| `list_tables` | `READ_SCHEMA` |
| `get_table_schema` | `READ_SCHEMA` |
| `select_rows` | `READ_DATA` |
| `execute_readonly_query` | `READ_DATA` (+ SQL только класса read/SELECT) |
| `explain_query_plan` | `READ_DATA` |
| `execute_write_query` | `WRITE_DATA` (+ SQL только DML: INSERT/UPDATE/DELETE) |
| `get_database_stats` | `ADMIN` |

В v1 **отдельного DDL-tool нет**. Если в `execute_write_query` пришёл DDL-SQL → отказ (`statement_class_denied` / нужен `DDL`), даже при `WRITE_DATA`.  
Capability `DDL` зарезервирован под будущий явный tool (или расширение) — в конфиге можно выдать заранее, но v1 tools его не обслуживают без отдельного пути.

### 6.4 Класс SQL (вторая проверка на сыром SQL)

Сырой SQL принимают только `execute_readonly_query` / `execute_write_query` / `explain_query_plan`.  
Остальные tools (`list_*`, `select_rows`, …) **не** парсят произвольный SQL — параметры → безопасный путь в gateway.

**v1 классификация = AST Postgres, не «первое слово» текста.**  
Парсер — тот же, что у PostgreSQL (`libpg_query` / Python: `pglast`). Обходим дерево узлов; fail-closed.

| Класс | Как решаем (по AST, не по префиксу строки) | Capability |
|-------|---------------------------------------------|------------|
| `READ` | ровно 1 statement; только read-узлы (`Select` / `Values` / `Explain` без исполнения мутаций); **нет** Insert/Update/Delete/Merge **нигде**, в т.ч. внутри `WITH` | `READ_DATA` |
| `DML` | есть Insert/Update/Delete/Merge (в т.ч. modifying CTE) | `WRITE_DATA` |
| `DDL` | Create/Alter/Drop/Truncate/… | `DDL` |
| `ADMIN` | Vacuum/Reindex/Copy/Grant/… | `ADMIN` |
| `UNKNOWN` | parse fail, >1 statement, `BEGIN`/`COMMIT`/… от агента, сомнение | **отказ** |

Пример, который ломает text-classifier, но **не** AST:

```sql
WITH x AS (DELETE FROM users RETURNING *)
SELECT * FROM x;
```

→ класс `DML` (внутри есть `Delete`), не `READ`. Readonly-tool → `denied`.

**Правила tool ↔ класс (v1):**

| Tool | Принимает |
|------|-----------|
| `execute_readonly_query` | только класс `READ` |
| `explain_query_plan` | только класс `READ` (без `EXPLAIN ANALYZE` мутаций) |
| `execute_write_query` | только **чистый top-level DML**: корень `Insert` / `Update` / `Delete`; без DDL/ADMIN; **modifying CTE + наружный SELECT — deny** (упростили blast radius) |

Нельзя провести `DROP` под видом write; нельзя провести `DELETE` под видом «SELECT с CTE».

### 6.4.1 Слои защиты SQL (defense in depth)

Один фильтр не считается достаточным (урок Datadog / archived reference Postgres MCP: `COMMIT; DROP…` вылезал из «read-only» обёртки).

| # | Слой | v1 |
|---|------|-----|
| 1 | Structured tools без свободного SQL | главная поверхность |
| 2 | AST guard (`pglast`) до БД | MUST |
| 3 | Один statement + execute без multi-statement string | MUST (анти-`COMMIT; DROP`) |
| 4 | Read path: `BEGIN READ ONLY` + `SET LOCAL` timeouts / max bytes | MUST |
| 5 | Роль Postgres с минимальными GRANT (RO для read-only демо) | MUST в deploy-доке |
| 6 | Capabilities + event без payload | уже в продукте |

Роль БД — несущий замок: баг в app-guard не должен давать `DROP`, если у роли нет прав.

### 6.5 Пример конфига

```json
{
  "max_rows": 100,
  "agents": {
    "agent_abc123": {
      "permissions": ["READ_SCHEMA", "READ_DATA"]
    },
    "agent_fin_5678": {
      "permissions": ["READ_SCHEMA", "READ_DATA", "WRITE_DATA"]
    },
    "agent_dba_999": {
      "permissions": ["READ_SCHEMA", "READ_DATA", "WRITE_DATA", "DDL", "ADMIN"]
    }
  }
}
```

- Ключ объекта = `agent_id` (whitelist).  
- Нет ключа → отказ, события нет.  
- Нет поля `permissions` → default `["READ_SCHEMA", "READ_DATA"]` (безопасный минимум).  
- Пустой `permissions: []` → в whitelist, но любой tool → `denied` + событие.

### 6.6 Что режется чем

| Проверка | Результат |
|----------|-----------|
| Нет / битый Bearer | отказ, события нет |
| `agent_id` ∉ `agents` | отказ, события нет |
| Нет capability на tool | отказ + событие `denied` |
| SQL-класс не покрыт permissions (напр. DDL при только `WRITE_DATA`) | отказ + событие `denied` |
| Permissions ок, Postgres ок/ошибка | событие `ok` / `error` |

### 6.7 Политика на диске — без рестарта MCP

`agents.json` **не** «залили при старте и забыли».  
Минимум v1: кэш в памяти + периодическая проверка (TTL / mtime файла) + **atomic replace** снимка.  
Сняли агента с whitelist → следующий tool call уже отказ, без рестарта процесса.

### 6.8 Потом (не v1)

- отдельный `execute_ddl_query` под `DDL`  
- `deny_tables` / `allow_tables` / schema allowlist в AST  
- разные `max_rows` / timeouts на агента  
- разрешение modifying-CTE на write-tool (сейчас deny)  
- SQL cost / EXPLAIN gates  
- push/pubsub инвалидации policy (сейчас — pull TTL/mtime)  

**Уже в v1 (не откладываем):** AST-классификация через парсер Postgres, single-statement, READ ONLY txn, session timeouts.

---

## 7. Система событий действий агента

Этот раздел — **только** про audit личности агента: `AgentActionEvent`, EventBus и демо-консоль `ConsoleSink`.  
Технические логи процесса сюда **не входят** → **§8**.

### 7.1 Что в ядре, чего нет

**Ядро ивентов делает ровно одно:** появляется событие одной схемы — и только если уже опознан **разрешённый** агент.

**Событие НЕ создаётся**, если не получилось идентифицировать разрешённого агента:

- нет / битый / просроченный паспорт, verify fail, неверные claims  
- паспорт ок, но `agent_id` **нет** в whitelist  

В этих случаях агенту всё равно возвращается понятный отказ — просто без audit-события.

В функционал ивентов **не входят**: консоль, webhook, запись в чью-то БД / SIEM. Это сторонний код, который *читает* событие, если оно было.

Следствия:

- Нельзя подменять **аудит действий агента** через `print` внутри tool’ов мимо событий.
- Консольный лог **действий агента** (`ConsoleSink`) **полностью зависит от событий**: нет события → в эту консоль ничего не уходит.
- Разработчик подключает свой обработчик тем же способом: слушает событие → пишет к себе.

### 7.2 Один формат — и **без** тела ответа агенту

Все события одинаковы по структуре. В заметке фиксируем факт действия, **не копию того, что ушло модели**.

| Канал | Что видит |
|-------|-----------|
| Агент (MCP tool result) | полный полезный ответ (строки, текст ошибки для LLM) |
| Событие / webhook / консоль-sink | кто · что вызвал · `status` · коды/метрики — **без rows, без текста ответа** |

**Почему:** полный `SELECT * FROM users` в EventBus → webhook = утечка PII/секретов во второй контур. Аудиту достаточно «agent X сделал select_rows → ok».

Меняется содержимое:

1. **кто** — `agent_id`  
2. **что запросил** — tool + args (без паспорта; сырой SQL в args допустим как факт запроса, не как dump результата)  
3. **чем кончилось** — `status` + машинный `outcome` (коды/счётчики), **не** payload агента  

### 7.3 Схема события (всегда одна)

| Поле | Смысл |
|------|--------|
| `event_id` | уникальный id |
| `ts` | время UTC |
| `agent_id` | из паспорта |
| `request` | `{ "tool": "...", "args": { ... } }` |
| `status` | `ok` \| `error` \| `denied` |
| `outcome` | **краткая карточка исхода**, не ответ агенту (см. ниже) |

**MUST NOT** в событии: `response`, `rows`, `payload`, полный текст сообщения для LLM, любые ячейки результата.

`outcome` (только метаданные):

| Поле | Когда |
|------|--------|
| `reason_code` | `capability_denied` / `statement_class_denied` / `database_fault` / … |
| `missing_capabilities` | deny по permissions |
| `statement_class` | deny/класс SQL |
| `rows_count` | ok на data-tools (число строк, **не** строки) |
| `affected_rows` | ok на DML (если известно) |

Служебное: `duration_ms`, `meta.domain`, `meta.request_id`.

Пример — deny capability:

```json
{
  "event_id": "…",
  "ts": "2026-07-31T16:00:00Z",
  "agent_id": "agent_abc123",
  "request": { "tool": "execute_write_query", "args": { "sql": "…" } },
  "status": "denied",
  "outcome": {
    "reason_code": "capability_denied",
    "missing_capabilities": ["WRITE_DATA"]
  }
}
```

Пример — DDL через write-tool:

```json
{
  "event_id": "…",
  "ts": "2026-07-31T16:00:01Z",
  "agent_id": "agent_fin_5678",
  "request": { "tool": "execute_write_query", "args": { "sql": "DROP TABLE orders" } },
  "status": "denied",
  "outcome": {
    "reason_code": "statement_class_denied",
    "statement_class": "DDL"
  }
}
```

Пример — успех select (строк в event **нет**):

```json
{
  "event_id": "…",
  "ts": "2026-07-31T16:00:01Z",
  "agent_id": "agent_abc123",
  "request": { "tool": "select_rows", "args": { "schema": "public", "table": "orders", "limit": 10 } },
  "status": "ok",
  "outcome": { "rows_count": 10 }
}
```

Агенту при этом уходит обычный полный JSON с `rows` — только по MCP, не через событие.

### 7.4 Демо-консоль и сторонние sinks (не ядро ивентов)

Sink’и получают **ту же безопасную** схему. Нельзя «дописать полный ответ в webhook» из ядра — ядро его в event не кладёт.

#### Что поставляем в этом репозитории

| Артефакт | Роль |
|----------|------|
| `EventBus` + `AgentActionEvent` | ядро: факт после whitelist |
| **`ConsoleSink`** | **демо-консоль** карточек действий агента — показывает возможность системы ивентов |
| Webhook / SIEM / своя БД | **не делаем.** Пишет интегратор у себя через `bus.subscribe` |

Демо-консоль (`ConsoleSink`) печатает событие как есть (карточка), не дамп tool result. Это не обязательный runtime LIME — только showcase надстройки над ивентами.

**Закон надстройки (жёстко):**

| Направление | Разрешено? |
|-------------|------------|
| Ядро → EventBus.emit → sink | да |
| Sink → меняет Result tool / DB / policy / auth | **нет** |
| Sink → импорт application services для «дожать» audit | **нет** |
| Удалить ConsoleSink / выключить флаг | сервер и pipeline **живы** |
| Мы (maintainers showcase) обязаны поставить WebhookSink | **нет** — out of scope |

Sink — односторонний consumer. Ошибка sink не меняет Result агенту (техлог ошибки — §8, не этот раздел).

---

## 8. Технические логи процесса (process observability)

Отдельный отдел от §7. Здесь — **жизнь MCP-сервера** (structured logs + metrics + correlation), а не журнал действий агента.

**Позиция продукта:** open-source showcase LIME; observability — версионируемый публичный контракт.  
**Не путать:** ConsoleSink / `AgentActionEvent` = §7. Этот раздел = ops-журнал процесса.  
Норматив: [ADR-003](./ADR-003-process-observability.md) · TDD §9.6.

### 8.1 Чем это не является

- не EventBus и не ConsoleSink  
- не обёртка «только на tools/call»  
- не замена аудита агента (§7)

Pre-auth отказы (битый паспорт, не в WL) **видны здесь** и **не** порождают событие §7.

### 8.2 Два канала этого отдела + граница с §7

| Канал | Вопрос | Когда | Где код |
|-------|--------|-------|---------|
| **A. Process log** | Что делает **сервер**? | всегда | `bootstrap/observability` → stderr/stdout |
| **B. Process metrics** | Сколько / как быстро / сколько fail? | всегда | `observability/metrics` |
| *(граница)* **§7 Agent audit** | Что сделал **опознанный агент**? | только после WL | `Emit*` → EventBus → ConsoleSink / свой sink |

```text
  layers ──► observability.log / metrics  ──► JSONL process stream   (§8)
  Invoke ──emit──► EventBus ──► ConsoleSink ──► agent audit cards    (§7)
```

**MUST NOT:** смешивать A/B с §7 в один формат.  
**MUST NOT:** sink или metrics менять UC / `AgentReply`.

### 8.3 Продуктовые MUST

1. **Один публичный facade** `bootstrap.observability` — `configure` / `get_logger` / `log` / `metrics` / context bind. Запрещены ad-hoc `print`, голый `logging.getLogger` вне namespace пакета.
2. **Versioned log schema** `lime.mcp.process_log.v1` — `schema`, `ts`, `level`, `component`, `event` (+ correlation). Ломающее изменение → `v2` + ADR.
3. **Default format = JSON Lines**. Опционально `console` (key=value) — тот же schema.
4. **Full B03 triad:** logs **и** metrics **и** correlation.
5. **Покрытие:** CLI/serve, lifespan, identity, policy, establish, authorize, DB, emit/bus, MCP transport, shutdown (+ metrics.summary).
6. **Domain чистый (A05):** в `domain/**` нет observability I/O.
7. **Correlation:** `request_id` на call; после verify — `agent_id`; тот же id → `AgentActionEvent.meta.request_id` (§7), когда событие есть.
8. **W3C Trace Context (best-effort):** `traceparent` → `trace_id` / `parent_span_id`; без обязательного OTel SDK в v1.
9. **Err (A10):** `invariant_id`/`code` + safe context + `request_id`.
10. **Redaction:** MUST NOT — Bearer/JWT, `POSTGRES_URL`, password, rows/payload агенту, полный policy dump. SQL на INFO — нет; DEBUG — `sql_preview≤80` или `args_keys`.
11. **Metrics:** counters + histograms; snapshot API; `metrics.summary` на shutdown. Нет REST `/metrics`/`/health` в v1.
12. **Configure только при bootstrap/`serve`.**
13. **Contributor law:** critical path зовёт facade.

### 8.4 Schema `lime.mcp.process_log.v1`

| Field | Тип | Смысл |
|-------|-----|--------|
| `schema` | string | всегда `lime.mcp.process_log.v1` |
| `ts` | string | ISO-8601 UTC `Z` |
| `level` | string | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `component` | string | `serve` \| `identity` \| `policy` \| `establish` \| `authorize` \| `db` \| `events` \| `mcp` \| `metrics` |
| `event` | string | стабильное имя (`tools.call.done`, `preauth.fail`, …) |

Корреляция: `request_id`, `agent_id`, `trace_id`, `parent_span_id`.  
Исход: `status` / `outcome` / `invariant_id` / `code` / `duration_ms` / `tool` / `op`.  
Deny-list: ADR-003 / TDD §9.6.

### 8.5 Metrics catalog (v1)

| Metric | Type | Labels | Когда |
|--------|------|--------|--------|
| `mcp_tools_call_total` | counter | `tool`, `outcome` | `tools/call` done |
| `mcp_preauth_fail_total` | counter | `code` | pre-auth отказ |
| `mcp_authorize_deny_total` | counter | `tool`, `code` | capability/SQL deny |
| `mcp_db_op_total` | counter | `op`, `status` | gateway op |
| `mcp_db_op_duration_ms` | histogram | `op` | gateway op |
| `mcp_tools_call_duration_ms` | histogram | `tool` | tools/call wall |
| `mcp_emit_total` | counter | `status` | agent event emit |
| `mcp_sink_error_total` | counter | — | sink exception |
| `mcp_jwks_warmup_total` | counter | `status` | lifespan warmup |
| `mcp_pool_open_total` | counter | `status` | pool open |

Buckets ms: `[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000]`.

### 8.6 Покрытие

| Зона | Log events (INFO+) | Metrics |
|------|--------------------|---------|
| Serve / CLI | `serve.start/stop`, `config.error` | — |
| Lifespan | `jwks.warmup`, `pool.open/close` | warmup/pool |
| Identity | `verify.ok` / `verify.fail` | — |
| Policy | `policy.load/reload/soft_keep` | — |
| Establish | `preauth.fail`, `context.ok` | `mcp_preauth_fail_total` |
| Authorize | `authorize.allow/deny` | deny counter |
| DB | `db.op` | db counters + histogram |
| Emit / bus | `emit`, `sink.error` | emit / sink_error |
| MCP | `tools.call.start/done`, `tools.list`, `unknown_tool` | call total + duration |
| Shutdown | `metrics.summary` | snapshot dump |

### 8.7 Пример (JSONL)

```json
{"schema":"lime.mcp.process_log.v1","ts":"2026-08-04T12:00:00.000Z","level":"INFO","component":"mcp","event":"tools.call.start","request_id":"r1","tool":"select_rows"}
{"schema":"lime.mcp.process_log.v1","ts":"2026-08-04T12:00:00.005Z","level":"INFO","component":"identity","event":"verify.ok","request_id":"r1","agent_id":"agent_ok"}
{"schema":"lime.mcp.process_log.v1","ts":"2026-08-04T12:00:00.018Z","level":"INFO","component":"mcp","event":"tools.call.done","request_id":"r1","tool":"select_rows","outcome":"ok","duration_ms":18}
```

Pre-auth (события §7 **нет**, техлог §8 **есть**):

```json
{"schema":"lime.mcp.process_log.v1","ts":"2026-08-04T12:01:00.000Z","level":"INFO","component":"establish","event":"preauth.fail","request_id":"r2","invariant_id":"identity.passport_missing"}
```

### 8.8 Env

| Env | Default | Смысл |
|-----|---------|--------|
| `LIME_MCP_LOG_LEVEL` | `INFO` | уровень process log |
| `LIME_MCP_LOG_FORMAT` | `json` | `json` / `console` |
| `LIME_MCP_LOG_STREAM` | `stderr` | `stderr` / `stdout` |
| `LIME_MCP_METRICS` | `1` | `0` = metrics no-op |

**Не путать** с `ENABLE_CONSOLE_EVENT_SINK` (§7 ConsoleSink).

### 8.9 Acceptance

1. `serve` → JSONL: start → warmup → pool → calls → `metrics.summary` → stop.  
2. Битый Bearer → `preauth.fail` + metric; **нет** `AgentActionEvent` / ConsoleSink.  
3. Нет JWT / `POSTGRES_URL` / rows / Bearer.  
4. `ENABLE_CONSOLE_EVENT_SINK=0` не глушит §8.  
5. Удаление `console_sink.py` не ломает pipeline и §8.  
6. `ProcessMetrics.snapshot()` отражает deny/ok.  
7. Один `request_id` связывает строки §8 и (если есть) `event.meta.request_id` (§7).  
8. Нет HTTP `/health` / `/metrics` в v1.

---

## 9. Что за дверью: инструменты к Postgres (v1)


К инструментам допускаем только после паспорта + whitelist + нужного capability (+ класс SQL на сырых запросах).

### Просмотр схемы — `READ_SCHEMA`

1. `list_schemas()`  
2. `list_tables(schema="public")`  
3. `get_table_schema(schema="public", table=...)`  

### Данные — `READ_DATA` / `WRITE_DATA`

4. `select_rows(schema, table, columns?, limit?, offset?)` — `READ_DATA`  
5. `execute_readonly_query(sql, limit?)` — `READ_DATA`, только SQL класса `READ`, txn read-only  
6. `execute_write_query(sql, target_table?)` — `WRITE_DATA`, только DML (`INSERT`/`UPDATE`/`DELETE`); DDL через этот tool запрещён  

### Сервис

7. `explain_query_plan(sql)` — `READ_DATA`  
8. `get_database_stats()` — `ADMIN`  

Wire arg names match Authorize / `ToolName` catalog (`schema` / `table` / `sql` — not `schema_name` / `sql_query`).

Дополнительная защита (обязательно):

- **AST** fail-closed до БД (см. §6.4); WRITE_DATA ≠ DDL; CTE-`DELETE` ≠ READ  
- structured tools без SQL — предпочтительный путь  
- один statement / no agent txn control  
- `max_rows` / LIMIT; **session timeouts** + `max_result_bytes` (READ ONLY не спасает от `pg_sleep`)  
- read path: `BEGIN READ ONLY`  
- deploy: least-privilege DB role  
- ошибки БД для модели без утечки инфры  

Детали: TDD §5.5 (AST), §9.3 (gateway), adversarial suite.

Auth boundary (где Bearer, как тестировать без HTTP) — [ADR-001](./ADR-001-mcp-authentication-boundary.md).

---

## 10. Переменные окружения

```env
# личность агентов (LIME)
LIME_EXPECTED_DOMAIN=your-corporate-domain.com
LIME_JWKS_URL=https://lime.pics/.well-known/jwks.json
AGENTS_POLICY_PATH=./config/agents.json
# политика: как часто перечитывать файл (секунды)
POLICY_RELOAD_TTL_SECONDS=60

# ресурс за дверью (учётка MCP-сервиса)
POSTGRES_URL=postgresql://user:password@localhost:5432/dbname
# защита от DoS / долгих запросов агента
PG_STATEMENT_TIMEOUT=5s
PG_LOCK_TIMEOUT=2s
PG_IDLE_IN_TRANSACTION_TIMEOUT=10s
PG_MAX_RESULT_BYTES=1048576

# демо audit агента (§7) — только ConsoleSink; своих webhook-систем в пакете нет
# ENABLE_CONSOLE_EVENT_SINK=1

# process observability (§8 — не audit агента §7; ADR-003)
LIME_MCP_LOG_LEVEL=INFO
LIME_MCP_LOG_FORMAT=json
# LIME_MCP_LOG_STREAM=stderr
# LIME_MCP_METRICS=1
```

Точный URL JWKS при реализации сверить с актуальным контрактом lime.pics.

**Deploy (несущий замок):** роль в `POSTGRES_URL` — минимум прав под сценарий (для read-only демо — только `CONNECT` / `USAGE` / `SELECT`, без DDL/DML grants). App AST — defense in depth, не замена GRANT.

**Потоки наружу (не путать):**

| Env / канал | Что пишет | Кто поставляет |
|-------------|-----------|----------------|
| `LIME_MCP_LOG_*` + observability | JSONL жизни сервера + metrics.summary | этот репозиторий (**§8**, P5.1) |
| `LIME_MCP_METRICS` | in-process counters/histograms | этот репозиторий (**§8**, P5.1) |
| `ENABLE_CONSOLE_EVENT_SINK` + ConsoleSink | JSONL карточек **событий агента** | этот репозиторий (**§7** демо) |

---

## 11. Чего в первой версии не делаем

- Админку политик в UI (хватает JSON-конфига + TTL/mtime reload)
- Push/pubsub инвалидации policy (есть pull TTL/mtime)
- Stdio MCP / auth только на handshake без Bearer на call ([ADR-001](./ADR-001-mcp-authentication-boundary.md))
- Разные Postgres-тенанты в одном процессе
- Table/schema ACL в политике; SQL cost model; modifying-CTE на write-tool
- Text/regex «классификатор» вместо AST (в v1 **запрещён** как SSOT)
- Хранение аудита и доставку в webhook/консоль **внутри ядра** ивентов (ядро только emit; ConsoleSink — отдельный демо-subscriber)
- **WebhookSink / любой outbound audit HTTP** — out of scope maintainers; делает интегратор у себя
- REST `/health` / `/metrics` в v1 (observability = JSONL + snapshot; ADR-003)
- Режим «без паспорта для удобства» в проде
- Эксплуатацию этого пакета как прод-сервис LIME (это showcase на GitHub)

---

## 12. Как поймём, что получилось

1. Без паспорта или вне whitelist агент **не** трогает SQL и **не** оставляет событие.  
2. У опознанного агента однотипный след: `agent_id` + `request` + `status`/`outcome` — **без** тела ответа агенту.  
3. Демо-логер действий агента читает только события; полный tool result в консоль агентского аудита не дублируется.  
4. Process observability (§8 / ADR-003): JSONL schema v1 + metrics snapshot; pre-auth отказы видны; нет JWT/URL БД/rows; нет `/metrics` HTTP.  
5. Выключили ConsoleSink — события всё ещё emit’ятся в bus (если кто-то подписан), pipeline жив; process log/metrics живы.  
6. Без `WRITE_DATA` нельзя DML; с `WRITE_DATA` без `DDL` нельзя `DROP`/`ALTER` через write-tool.  
7. `WITH (DELETE…) SELECT` на readonly-tool → deny (AST), не «как будто SELECT».  
8. `COMMIT; DROP…` / multi-statement → deny до БД.  
9. Долгий SQL упирается в session timeouts, не только в READ ONLY.  
10. Смена `agents.json` подхватывается без рестарта (TTL/mtime).  
11. Путь: паспорт lime.pics → дверь → действие в БД.

---

## 13. Как будем собирать (позже)

- Пакет на Python (Marketing или sdk)  
- Цепочка: паспорт → whitelist → permissions → (класс SQL) → действие → событие  
- Тесты: битый паспорт / не в WL → нет события; capability deny / CTE-DELETE / multi-stmt / DROP via write / ok / SQL error → событие; adversarial AST suite  

---

## 14. Одной фразой

> Open-source showcase: агент с паспортом LIME стучится в Postgres по MCP. Whitelist и permissions решают, что можно; след — одно событие без копии ответа. `ConsoleSink` — демо системы ивентов в репо; webhook/SIEM пишет интегратор у себя. Process observability — контракт жизни сервера (ADR-003). Пакет не эксплуатируется как прод LIME.
