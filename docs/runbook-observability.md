# Observability runbook

## Logs (structlog)

- Set `WEEKCHEF_LOG_JSON=true` for one JSON object per line (suitable for Loki / Cloud Logging).
- `WEEKCHEF_LOG_LEVEL` defaults to `INFO`.
- Logs include `correlation_id`, `user_id` (ключ профиля / сессии), `dialogue_id`, `turn_index` when the request came through the Streamlit NL path or the CLI `/plan` orchestrator path.
- **Do not** expect raw user message text in logs; only `intake_sha` (short hash) on orchestrator events.
- **LLM JSON validation failures:** set `WEEKCHEF_LLM_VALIDATION_PREVIEW_CHARS` to a small positive number (e.g. `400`) to emit a structured `llm_json_validation_failed` log line with a **truncated** raw model reply when Pydantic/JSON parsing fails inside `complete_json_*`. The preview can still echo user wording from `intent_summary` — use only in dev and short retention.

## Traces (OpenTelemetry)

1. Set `WEEKCHEF_OTEL_ENABLED=true`.
2. Optionally `WEEKCHEF_OTEL_TRACES_CONSOLE=true` for local debugging (spans printed to the console).
3. For Grafana Tempo / OTLP HTTP collector: set `OTEL_EXPORTER_OTLP_ENDPOINT` (e.g. `http://localhost:4318`) and `OTEL_SERVICE_NAME=weekchef`. Use `OTEL_EXPORTER_OTLP_INSECURE=true` for local HTTP without TLS.
4. Restart the Streamlit app or CLI after changing env.

### Trace layout

- One **trace** per user message / CLI pipeline run.
- Root span: `user_turn` (natural language orchestrator) or nested spans under the weekly pipeline: `INTAKE`, `ENRICH`, `PLAN_LLM` / `PLAN_DETERMINISTIC`, `AGGREGATE`, `VALIDATE`, `SHOPPING`.
- Each HTTP LLM call: child span `llm.completion` with `weekchef.step`, `weekchef.prompt_version`, `gen_ai.request.model`, token usage when the provider returns it.

### Filtering a multi-turn dialogue

All turns in one conversation share `weekchef.dialogue_id` (stored in `weekchef_sessions.state_json`). In Tempo / Grafana TraceQL, filter on that attribute and sort by time or `weekchef.turn_index`.

## Metrics (OTel)

- Histogram `weekchef.plan.duration_ms` (labels `valid`, `fallback_used`) — emitted when `run_weekly_plan_pipeline_with_shopping` finishes.
- Histogram `weekchef.validate.duration_ms` — длительность только фазы `validate_plan` внутри pipeline.
- Counters: `weekchef.llm.completions`, `weekchef.llm.json_retry`, `weekchef.llm.unavailable` (labels `weekchef.step`, `reason`: `nonrecoverable` | `schema_retries_exhausted` | `transport_retries_exhausted`), `weekchef.llm.fallback_model_calls` (HTTP-вызовы со второй моделью в цепочке), `weekchef.validate.fail`, `weekchef.get_recipes.calls`; histogram `weekchef.get_recipes.duration_ms`.
- Enable export with `WEEKCHEF_OTEL_METRICS_CONSOLE=true` and/or the same OTLP endpoint (metrics path is configured by the HTTP exporter).

## Langfuse (optional)

Requires optional dependency: `pip install -e ".[langfuse]"`.

1. Set `WEEKCHEF_LANGFUSE_ENABLED=true`.
2. Set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and optionally `LANGFUSE_HOST` (default Cloud: `https://cloud.langfuse.com`; self-host — URL вашего инстанса).
3. Restart the Streamlit app / CLI. The OpenAI-compatible client is swapped for `langfuse.openai` when the flag and keys are set; each `chat.completions.create` sends a generation to Langfuse with `name` = LLM step and `metadata` (`weekchef.correlation_id`, `weekchef.dialogue_id`, `weekchef.user_id`, `weekchef.prompt_version` when present).
4. **Flush:** buffered observations are flushed after each `complete_json_*` call and after each NL `process_user_turn`, so short-lived processes (CLI) do not lose traces.

**OTel:** Langfuse and OpenTelemetry can run together; отключайте OTel только если это осознанное решение.

**PII / governance:** Langfuse получает **полные `messages`** (включая пользовательский текст intake). Это отдельно от structlog и политики логов. Используйте dev-only, self-host с masking, или отключайте `WEEKCHEF_LANGFUSE_ENABLED` в проде без явного согласования — см. [governance.md](governance.md).

## Retention / governance

See [governance.md](governance.md): short log retention for PoC, no calendar event titles or raw allergies in logs.
