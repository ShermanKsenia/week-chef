"""Observability: structured logs, traces, metrics."""

from __future__ import annotations

from weekchef.config import Settings

from weekchef.observability.context import (
    get_correlation_id,
    get_dialogue_id,
    get_turn_index,
    get_user_key,
    otel_common_attributes,
    request_context,
)
from weekchef.observability.dialogue import OBS_DIALOGUE_ID, OBS_TURN_INDEX, prepare_turn_patch, reset_dialogue_state
from weekchef.observability.logging_setup import configure_logging, get_logger
from weekchef.observability.metrics import (
    inc_get_recipes_result,
    inc_llm_completion,
    inc_llm_fallback_model,
    inc_llm_json_retry,
    inc_llm_unavailable,
    inc_validate_fail,
    record_get_recipes_ms,
    record_plan_finished,
    record_validate_duration_ms,
)
from weekchef.observability.otel import configure_metrics, configure_tracing, get_meter, get_tracer
from weekchef.observability.redact import intake_text_hash
from weekchef.observability.spans import phase_span, user_turn_root_span

__all__ = [
    "OBS_DIALOGUE_ID",
    "OBS_TURN_INDEX",
    "configure_logging",
    "configure_metrics",
    "configure_observability",
    "configure_tracing",
    "get_correlation_id",
    "get_dialogue_id",
    "get_logger",
    "get_meter",
    "get_tracer",
    "get_turn_index",
    "get_user_key",
    "inc_get_recipes_result",
    "inc_llm_completion",
    "inc_llm_fallback_model",
    "inc_llm_json_retry",
    "inc_llm_unavailable",
    "inc_validate_fail",
    "intake_text_hash",
    "otel_common_attributes",
    "phase_span",
    "prepare_turn_patch",
    "record_get_recipes_ms",
    "record_plan_finished",
    "record_validate_duration_ms",
    "request_context",
    "reset_dialogue_state",
    "user_turn_root_span",
]


def configure_observability(settings: Settings) -> None:
    """Configure structlog + optional OpenTelemetry (idempotent)."""
    configure_logging(json_logs=settings.log_json, log_level=settings.log_level)
    configure_tracing(settings)
    configure_metrics(settings)
