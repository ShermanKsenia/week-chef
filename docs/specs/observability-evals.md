# Спецификация: Observability / Evals

## Метрики

### Реализовано в репозитории (OTel)

Имена инструментов см. [runbook-observability.md](../runbook-observability.md) и [src/weekchef/observability/metrics.py](../../src/weekchef/observability/metrics.py):

- **Latency:** гистограмма `weekchef.plan.duration_ms` (полный прогон `run_weekly_plan_pipeline_with_shopping`); `weekchef.get_recipes.duration_ms`; `weekchef.validate.duration_ms` (только фаза `validate_plan` внутри pipeline); длительность каждого HTTP-вызова LLM — в **трейсе** (`llm.completion`, span duration) и при необходимости агрегируется в бэкенде.
- **Счётчики:** `weekchef.llm.completions` (labels `weekchef.step`, `result`, `model`); `weekchef.llm.json_retry`; `weekchef.llm.unavailable` (`reason`: `nonrecoverable` | `schema_retries_exhausted` | `transport_retries_exhausted`); `weekchef.llm.fallback_model_calls` (HTTP-вызовы со второй моделью в цепочке); `weekchef.validate.fail` с `reason_code`; `weekchef.get_recipes.calls` с `result` / `code`.
- **Стоимость / токены:** атрибуты span `gen_ai.usage.prompt_tokens` / `gen_ai.usage.completion_tokens` на `llm.completion` при ответе провайдера (агрегированные метрики «на запрос» в коде пока не дублируются — при необходимости добавить histogram/counter отдельно).

### Желательно / будущие (пока не в коде)

- **Надёжность внешних API:** явная таксономия ошибок (`TIMEOUT`, `429`, `5xx`) **по каждому** tool — для `get_recipes` частично отражено в label `code`; для календарных tool — по аналогии при появлении экспорта.
- **Очередь / async:** при фоновом построении плана — глубина очереди, время ожидания, число stale-задач (**вне scope текущего PoC**).
- **Качество агента (продуктовое):** классификация фидбека по завершении недели, доля выполнённых дней; офлайн-оценки (DeepEval / RAGAS) на фиксированном наборе кейсов.

## Логи

### Контекст запроса (structlog)

Для путей Streamlit (NL-ход пользователя) и CLI `/plan` в каждую строку попадают из contextvars (см. [context.py](../../src/weekchef/observability/context.py)): `correlation_id`, `user_id`, при наличии `dialogue_id`, `turn_index`.

### Событийная модель

Вместо обязательных полей `step` / `tool` / `duration_ms` / `result` на **каждой** строке используется **имя события** (`user_turn_start`, `user_turn_plan_done`, `llm_json_validation_failed`, …) и дополнительные поля по смыслу события. Поля `duration_ms`, `result`, `error_code` отражены в **метриках** и **атрибутах span** там, где это критично для SLO.

Целевой вариант «единая строка с полным набором полей» — возможен через structlog processor в будущем; текущая схема согласована с [runbook-observability.md](../runbook-observability.md).

### LLM

Для вызовов LLM в трейсах/метриках: `model`, `weekchef.step`, `weekchef.prompt_version` (без полного текста промпта в логах).

### Запреты (governance)

**Запрещено:** сырой пользовательский ввод целиком, названия событий календаря, free-text аллергий — см. [governance.md](../governance.md).

**Допустимо:** короткий **хэш** запроса (`intake_sha`), коды отказов валидатора.

## SLO и «красная зона»

- Фиксированные пороги в конфиге или документе релиза: например доля ошибок LLM **> X%** за час, p95 latency полного плана **> Y s** — **сигнал к расследованию** (даже если алерт только ручной просмотр дашборда раз в день).
- **Error budget:** при превышении доли `LLM_UNAVAILABLE` (счётчик `weekchef.llm.unavailable`, в т.ч. `reason=schema_retries_exhausted` vs транспорт) — проверить квоты, ключи, статус провайдера.

## Трейсы

- Один **trace** на одно пользовательское сообщение (NL) или один CLI-прогон pipeline; корневой span **`user_turn`** для оркестратора NL (см. [spans.py](../../src/weekchef/observability/spans.py)).
- Вложенные фазы weekly pipeline (имена span = имя фазы): **`INTAKE`** (опционально), **`ENRICH`**, **`PLAN_LLM`** или **`PLAN_DETERMINISTIC`**, **`AGGREGATE`** (слоты календаря при включённом Google Calendar), **`VALIDATE`**, **`SHOPPING`** (если валидация прошла).
- Внутри планирования: дочерние span **`llm.completion`** на **каждый** HTTP-вызов к модели с атрибутами `weekchef.step`, `weekchef.prompt_version`, `gen_ai.request.model` и т.д.

Имена фаз в коде совпадают с [runbook-observability.md](../runbook-observability.md); переименование `PLAN_LLM` → абстрактный `PLAN` без согласования не делается (ломает существующие запросы TraceQL).

## Проверки / evals

- Синтетический профиль + фикстура календаря → план проходит `validate_plan`.
- **Регрессия промптов:** несколько золотых диалогов (JSON in/out) на `parse_input`.
- **Ручная выборка:** раз в спринт проверка N планов на нарушение строгих аллергенов (0 допуска).

## Реализация в репозитории

Практические шаги (env, OTLP, мульти-туровый `dialogue_id`): [runbook-observability.md](../runbook-observability.md).
