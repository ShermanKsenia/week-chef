# Разрывы реализации относительно дизайна

Этот документ фиксирует, где текущий код в `src/weekchef` **ещё не** совпадает с [system-design.md](../system-design.md) и [orchestrator.md](orchestrator.md). Обновляйте его по мере закрытия пунктов.

## Приоритет (итерация)

1. **Фасад оркестратора пользовательского хода** — единая точка `process_user_turn` ([`orchestrator_turn.py`](../../src/weekchef/orchestrator_turn.py)); все UI-входы (Streamlit: чат и действия в сессии) вызывают её, а не дублируют ветки INTAKE/PLAN.
2. **INTAKE + уточняющие вопросы** — после `parse_input` при непустом `missing_required_fields` не запускать ENRICH/PLAN; вызывать `generate_questions`, хранить черновик в session, ограничение раундов уточнений (спека: ≤5).
3. **Единый NL-вход** — свободный текст ведёт в тот же фасад; slash-команды остаются опционально для отладки/PoC.

## Сводная таблица (ожидание → факт)

| Ожидание (дизайн / спека) | Факт в коде (на момент введения фасада) |
| --- | --- |
| User → API → Orchestrator; оркестратор ведёт flow и state | Ранее: отдельные точки входа (команды/кнопки без общего «хода пользователя») вместо единого NL-фасада через Streamlit. |
| После INTAKE при missing fields → `generate_questions` и цикл диалога | Ранее: [`run_weekly_plan_pipeline`](../../src/weekchef/orchestrator_pipeline.py) не проверял `missing_required_fields` и всегда шёл в ENRICH → PLAN после parse. |
| Явные фазы PLAN_WEEK / PLAN_DAYS как в спеке | Реализация — `plan_simple_week` / `_plan_week_llm` без именования и разделения шагов как в спеке. |
| Централизованный retry валидатора на уровне оркестратора | Валидация есть; ограниченный retry «решением оркестратора» не выделен централизованно. |
| `analyze_feedback` и обновление предпочтений | Не реализовано в `src/`. |
| NL-перепланирование с `affected_dates` из текста | В Streamlit PoC перепланирование может вызываться с фиксированным `ReplanTrigger` вместо извлечения дат из текста. |
| REPLAN / REPLY как части одного контура с INTAKE | Частично; перепланирование не проходит через `process_user_turn` в PoC. |

## Что уже сделано (кратко)

- Фасад [`weekchef.orchestrator_turn`](../../src/weekchef/orchestrator_turn.py): `process_user_turn`, ответ `UserTurnResponse`, фазы INTAKE → (при полноте полей) пайплайн недели со shopping.
- Уточнения: при `missing_required_fields` планирование не вызывается; [`generate_questions`](../../src/weekchef/llm/generate_questions.py) (PoC-шаблон + задел под LLM); черновик parse и флаги в session.

## Долг (вне минимального PoC)

- Полное разделение PLAN_WEEK / PLAN_DAYS, `analyze_feedback`, богатый retry валидатора, NL-replan с областью дней, запись в календарь и confirm через тот же фасад.
