# Спецификация: Tools / APIs

Общие правила: 
1. Вызовы только через оркестратор
2. Аргументы проходят JSON-schema. При ошибке валидации JSON — повторный запрос до 3 раз. Если ошибка повторяется — сообщение пользователю и повторный запуск позже (см. оркестратор)
3. Чувствительные данные в логи не пишутся

## LLM API (вызов модели)
- **Назначение:** единая точка учёта **зависимости от провайдера LLM** (как у внешнего API): те же принципы таймаутов, ретраев и метрик, что у tools.
- **Таймаут:** задаётся в конфиге (например 60–120 s на запрос в зависимости от шага); отдельно от HTTP к рецептам/календарю.
- **Retry:** до `LLM_MAX_RETRIES` при `TIMEOUT`, `5xx`; при **429** — exponential backoff + учёт лимита `LLM_MAX_CONCURRENT`.
- **Ошибки (единый стиль с tools):** `TIMEOUT`, `UPSTREAM_429`, `UPSTREAM_5xx`, плюс при поддержке API: `LLM_UNAVAILABLE` (обе модели/квота), опционально `LLM_CONTENT_FILTER`, `LLM_REFUSAL`.
- **Fallback:** переключение на `LLM_FALLBACK_MODEL` по правилам `serving-config.md`; при полном отказе — `LLM_UNAVAILABLE`, без бесконечных ретраев.
- **Side effects:** запись в state только через оркестратор после валидации схемы ответа.

## Recipes: `get_recipes`
- **Вход:** `{ "filters": { ... }, "limit": number }`
- **Выход:** `{ "items": [...] }` или `{ "error": "...", "code": "..." }`
- **Timeout:** 10–15 s; **Retry:** до 3 раз с backoff при 429/5xx.
- **Side effects:** нет (read-only)

## Calendar: `calendar_free_busy` (read)
- **Вход:** `{ "from": iso, "to": iso }`
- **Выход:** `{ "free": [...] }` — только интервалы свободного времени
- **Timeout:** 10 s; **Retry:** до 3 раз
- **Side effects:** нет.

## Calendar: `calendar_propose_cook_events` (write, опционально PoC)
- **Вход:** `{ "events": [{ "start", "end", "title_template" }] }` — не исполняется без флага пользователя `confirm_apply`.
- **Выход:** `{ "applied": [...] }` или ошибка.
- **Timeout:** 15 s
- **Side effects:** создание событий в Google Calendar; лимит N событий на один запрос.

## Inventory: `inventory_get` / `inventory_update`
- **get:** чтение информации по продуктам у пользователя
- **update:** изменение записей по явному действию пользователя или применённому флагу от пользователя "приготовлено"

## Shopping List: `build_shopping_list`
- **Вход:** `{ "recipe_ids": [...], "servings": number, "subtract_inventory": bool }`
- **Выход:** `{ "lines": [{ "product", "qty", "unit" }] }`
- **Timeout:** 5 s; детерминированная логика, без внешних вызовов кроме загрузки рецептов при необходимости.

## Plan Validator: `validate_plan`
- **Вход:** `{ "weekly_plan", "calendar_snapshot", "state_excerpt" }`
- **Выход:** `{ "valid": bool, "reason_codes": [...] }`
- **Timeout:** 2 s; без сети.

## Ошибки (единый стиль)
- Общие: `TIMEOUT`, `UPSTREAM_429`, `UPSTREAM_5xx`, `VALIDATION_FAILED`, `NOT_FOUND`, `FORBIDDEN_WRITE`.
- LLM: `LLM_UNAVAILABLE`, опционально `LLM_CONTENT_FILTER`, `LLM_REFUSAL`.

## Защита
- Allowlist имён инструментов; запрет произвольных URL/команд из LLM.
- Write только после подтверждения и с лимитами.
