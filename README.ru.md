# lime-ref-postgres-mcp

[English](./README.md) · **Русский**

> Открытый пример, как работает **личность агента в [LIME](https://lime.pics)** — на живой двери к PostgreSQL через [MCP](https://modelcontextprotocol.io/).

Обычная схема «всем роботам один пароль от базы» здесь не используется. Агент приходит **со своим паспортом LIME** (заголовок `Authorization: Bearer`), сервер смотрит: кто это, есть ли он в списке допущенных, какие у него права — и только потом даёт MCP-инструменты к Postgres. Если агент уже опознан как «свой», по итогам вызова появляется **событие**: кто дернул инструмент и чем закончилось. Сам ответ агенту (строки из `SELECT` и т.п.) в событие **не кладётся**.

Это не прод LIME и не «наш хостинг». Это **разборный эталон** на GitHub: посмотреть паттерн, поднять у себя, при желании повесить свой аудит.

---

## Зачем вообще такой пакет

Проблема знакомая: агенты ходят в инфраструктуру без имени.

| Как часто бывает | Как здесь с LIME |
|------------------|------------------|
| Один `POSTGRES_URL` / ключ на всех ботов | У каждого агента свой `agent_id` из паспорта |
| В логах только «кто-то сходил в БД» | Можно сказать **какой именно агент** что сделал |
| Свой аудит или SIEM некуда воткнуть без перепила шлюза | Есть шина событий — подписываете свой обработчик |
| MCP-демо с «auth на словах» | Тот же паспорт LIME, что и к другим ресурсам платформы |

**Зачем мы это выложили:** чтобы технологию [LIME](https://lime.pics) было не стыдно показать на пальцах — цепочка «паспорт → пустили / не пустили → действие → след» на конкретной двери (Postgres по MCP). Не абстрактный слайд, а рабочий код.

Рядом по экосистеме LIME:

- Сайт и доки: [lime.pics](https://lime.pics)
- SDK агента (получить MCP JWT с доменом): [`lime-agents-sdk`](https://pypi.org/project/lime-agents-sdk/)
- SDK проверки паспорта на ресурсе: [`lime-mcp-server-sdk`](https://pypi.org/project/lime-mcp-server-sdk/) — этот сервер его использует

---

## Чем пакет является — и чем нет

| Да | Нет |
|----|-----|
| Публичный пример **паспорта агента LIME** на MCP → Postgres | Боевой сервис, который крутит сама команда LIME |
| Список агентов по умолчанию закрыт + права (capabilities) | «Один ключ — и вся база ваша» |
| В комплекте демо-подписчик `ConsoleSink` (карточки в консоль) | Готовые webhook’и и выгрузки в SIEM |
| Технические логи процесса сервера (ADR-003) | Путаница: карточки действий агента ≠ техлоги процесса |
| Отдельная папка-пакет, которую можно вынести | Жёсткая зависимость от остального монорепо |

**Важная путаница, которую лучше снять сразу.**  
Токен в `Authorization: Bearer` — это **паспорт агента**.  
`POSTGRES_URL` — это логин **самого MCP-сервиса** в Postgres. Это разные вещи: личность робота и учётка сервиса к базе.

---

## Что происходит на одном вызове

```
Агент с паспортом LIME  -- Bearer + tools/call -->  MCP /mcp
         │
         ▼
   1. Проверка JWT (ключи с lime.pics, проверка domain и aud)
         │ не прошёл → агенту отказ, события действия НЕТ
         ▼
   2. Есть ли agent_id в whitelist (config/agents.json)
         │ нет в списке → отказ, события НЕТ
         ▼
   3. Хватает ли прав + проверка класса SQL
         │ нельзя → ответ агенту + событие denied
         ▼
   4. Запрос в Postgres
         ▼
   5. Событие (ok / error) и ответ агенту
         │
         └── кто подписан на шину (ConsoleSink или ваш код)
```

Технические логи сервера могут писать и провалы на входе, и весь жизненный цикл вызова.  
**Событие «действие агента»** появляется только когда уже ясно: это наш allowlisted агент. Подробнее — [ADR-003](./ADR-003-process-observability.md).

---

## Что умеет

- Вход только с **паспортом LIME** на каждый `tools/call`
- Политика в JSON: кого пускаем, какие permissions, лимит строк, подхват файла с диска
- SQL не «на честном слове»: разбор через pglast и запрет лишних классов запросов
- Ровно восемь инструментов, единственный HTTP-путь — `/mcp`
- Шина событий без тела ответа агенту; свои обработчики через `subscribe`
- По желанию — карточки в stdout (`ConsoleSink`), чтобы увидеть систему ивентов
- Отдельно — JSON-логи процесса и простые metrics
- Локальный прогон качества: `prime_check` и CI

---

## Как поднять

Нужны Python 3.12+ и [uv](https://github.com/astral-sh/uv). Docker понадобится только если гоняете integration-тесты.

```bash
cd Marketing/lime-postgres-mcp   # или ваш клон пакета
uv sync --all-extras
cp .env.example .env             # пропишите LIME_* и POSTGRES_URL
# сделайте config/agents.json по образцу agents.example.json
# впишите реальный agent_id из паспорта LIME и права

uv run python -m lime_ref_postgres_mcp serve
# слушаем http://127.0.0.1:8000/mcp
```

Со стороны агента удобнее всего **lime-agents-sdk**. Он сам сходит в OAuth LIME и положит в JWT тот `domain`, который вы закрепили в `LIME_EXPECTED_DOMAIN`:

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

Просто проверить, что составка (identity, policy, БД) поднимается — без HTTP:

```bash
uv run python -m lime_ref_postgres_mcp
```

---

## Инструменты MCP

| Инструмент | Какое право нужно |
|------------|-------------------|
| `list_schemas` | `READ_SCHEMA` |
| `list_tables` | `READ_SCHEMA` |
| `get_table_schema` | `READ_SCHEMA` |
| `select_rows` | `READ_DATA` |
| `execute_readonly_query` | `READ_DATA` |
| `explain_query_plan` | `READ_DATA` |
| `execute_write_query` | `WRITE_DATA` |
| `get_database_stats` | `ADMIN` |

Паспорт передаётся **только** заголовком. В аргументы tool его класть нельзя и не нужно.

---

## Система событий — если хотите логировать «к себе»

Коротко по задумке: ядро **только сообщает факт** («агент X вызвал tool Y → ok/denied/error»). Куда это уедет дальше — ваше дело. Готовых webhook’ов в репозитории нет: у всех разные SIEM, очереди и политики, и мы не притворяемся универсальной доставкой.

### Что внутри карточки

- кто (`agent_id`) и чем кончилось (`ok` / `denied` / `error`)
- какой tool и с какими аргументами (**без** выборки из БД и без текста ответа агенту)
- коды причин, не хватившие права, класс SQL, счётчики строк — по ситуации
- служебное: `request_id`, домен, длительность, id события

Идея простая: в аудит не должен утекать `SELECT * FROM users`. Карточка — «кто и что пытался», не копия ответа.

### Когда карточки не будет

Паспорта нет или он битый, не поднялись ключи JWKS, агента нет в whitelist — агент получает отказ, а **события действия нет** (некого аудитить как «своего»). В техлоге процесса при этом обычно видно `preauth.fail`.

### Демо из коробки: ConsoleSink

Если `ENABLE_CONSOLE_EVENT_SINK=1` (так по умолчанию), при старте вешается обработчик, который печатает по одной JSON-строке на событие в stdout. Удобно понять форму. Если пишете только свой sink — выключите.

### Как повесить свой обработчик

Любая async-функция, которая принимает `AgentActionEvent`. Подписываетесь при сборке runtime:

```python
from lime_ref_postgres_mcp.bootstrap.container import build_scaffold_runtime
from lime_ref_postgres_mcp.domain.auditing.agent_action_event import AgentActionEvent

async def send_to_my_audit(event: AgentActionEvent) -> None:
    # своя таблица, Kafka, внутренний API — что угодно у вас
    await my_audit_store.write(
        agent_id=str(event.agent_id),
        tool=event.request.get("tool"),
        status=event.status,
        reason=(event.outcome.reason_code if event.outcome else None),
        request_id=(event.meta or {}).get("request_id"),
    )

runtime = build_scaffold_runtime()
runtime.event_bus.subscribe(send_to_my_audit)
# дальше отдаёте ASGI так же, как делает команда serve
```

На что обратить внимание:

1. Обработчик **только читает** событие. Обратно в authorize/invoke лучше не лезть.
2. Упал ваш sink — агенту всё равно должен уйти нормальный ответ tool’а. Ошибки подписчика шина глотает.
3. Не тащите тяжёлую работу в сам handler: быстрее отдать в свою очередь.
4. Техлогические логи сервера (`bootstrap.observability`) — **отдельная история**. Не мешайте их с аудитом действий агента.

Код демо: [`subscribers/console_sink.py`](./src/lime_ref_postgres_mcp/subscribers/console_sink.py).  
Контракт шины: [`application/ports/events.py`](./src/lime_ref_postgres_mcp/application/ports/events.py).

---

## Настройки

Берите [`.env.example`](./.env.example) и заполняйте. По смыслу:

| Переменная | Нужна? | Зачем |
|------------|--------|-------|
| `LIME_EXPECTED_DOMAIN` | да | Какой hostname должен быть в JWT (claim `domain`) |
| `LIME_JWKS_URL` | да | Откуда брать ключи проверки (обычно well-known lime.pics) |
| `LIME_EXPECTED_AUD` | нет | По умолчанию `mcp` |
| `POSTGRES_URL` | да | Куда ходит сервис MCP в Postgres |
| `AGENTS_POLICY_PATH` | нет | Файл whitelist, по умолчанию `./config/agents.json` |
| `POLICY_RELOAD_TTL_SECONDS` | нет | Как часто смотреть, не сменился ли файл |
| `ENABLE_CONSOLE_EVENT_SINK` | нет | Печатать демо-карточки в консоль |
| `LIME_MCP_LOG_*` / `LIME_MCP_METRICS` | нет | Техлоги и metrics процесса |
| `LIME_MCP_BIND_HOST` / `LIME_MCP_PORT` | нет | На каком адресе слушать `serve` |

Образец политики: [`config/agents.example.json`](./config/agents.example.json).

Переменной `WEBHOOK_URL` в пакете нет — и отдельного WebhookSink тоже.

---

## Как проверить, что ничего не сломали

```bash
uv run ruff check src tests
uv run mypy src
uv run pytest
uv run pytest tests/integration -m integration --no-cov -o addopts=

uv run python -m scripts.prime_check
uv run python -m scripts.prime_check --list
```

CI лежит рядом: [`.github/workflows/prime_check.yml`](./.github/workflows/prime_check.yml) — его же можно унести в отдельный репозиторий пакета.

---

## Куда читать дальше

| Файл | О чём |
|------|--------|
| [PRD.md](./PRD.md) | Замысел, модель доступа, правила событий |
| [TDD.md](./TDD.md) | Как устроены слои и модули |
| [ADR-001](./ADR-001-mcp-authentication-boundary.md) | Где проходит граница auth на MCP |
| [ADR-003](./ADR-003-process-observability.md) | Логи процесса, metrics, корреляция |
| [docs/verification/](./docs/verification/) | Отчёты по этапам сборки (Day0 → P6) |

---

## Как разложено в репозитории

```
src/lime_ref_postgres_mcp/
  domain/           # правила доступа, SQL-guard, форма события
  application/      # сценарий вызова: опознать → разрешить → сделать → записать след
  infrastructure/   # проверка JWT, JSON-политика, asyncpg, шина
  presentation/mcp/ # HTTP MCP на /mcp
  subscribers/      # демо ConsoleSink
  bootstrap/        # env, сборка, технологи процесса
config/
scripts/prime_check
tests/
```

---

## Статус

По плану сборки дошли до **P6**: CI зелёный, SBOM на месте. Пакет рассчитан как публичный образец «агент LIME → MCP → Postgres».

Мы **не** крутим его как прод LIME и **не** обещаем готовые исходящие webhook-интеграции.

---

## Лицензия

Смотрите [`pyproject.toml`](./pyproject.toml).
