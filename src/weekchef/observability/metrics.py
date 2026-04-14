"""OpenTelemetry metrics (histograms / counters) — instruments created once."""

from __future__ import annotations

from typing import Any

from weekchef.observability.otel import get_meter

_instruments: dict[str, Any] = {}


def _counter(name: str, description: str):
    key = f"c:{name}"
    if key not in _instruments:
        _instruments[key] = get_meter().create_counter(name, description=description)
    return _instruments[key]


def _histogram(name: str, unit: str, description: str):
    key = f"h:{name}"
    if key not in _instruments:
        _instruments[key] = get_meter().create_histogram(name, unit=unit, description=description)
    return _instruments[key]


def _norm_reason(code: str) -> str:
    if len(code) > 64:
        return code[:61] + "..."
    return code


def record_plan_finished(*, duration_ms: float, valid: bool, fallback_used: bool) -> None:
    """Emit histogram for one ``run_weekly_plan_pipeline_with_shopping`` completion."""
    hist = _histogram(
        "weekchef.plan.duration_ms",
        "ms",
        "Weekly plan pipeline duration",
    )
    hist.record(
        duration_ms,
        {
            "valid": str(valid).lower(),
            "fallback_used": str(fallback_used).lower(),
        },
    )


def inc_llm_completion(*, step: str, result: str, model: str = "") -> None:
    c = _counter("weekchef.llm.completions", "LLM JSON completion outcomes")
    c.add(
        1,
        {
            "weekchef.step": step[:64],
            "result": result,
            "model": (model or "unknown")[:128],
        },
    )


def inc_llm_json_retry(step: str) -> None:
    c = _counter("weekchef.llm.json_retry", "JSON schema retry attempts")
    c.add(1, {"weekchef.step": step[:64]})


def inc_validate_fail(reason_codes: list[str]) -> None:
    c = _counter("weekchef.validate.fail", "validate_plan failures")
    for code in (reason_codes or [])[:10]:
        c.add(1, {"reason_code": _norm_reason(str(code))})


def record_validate_duration_ms(duration_ms: float) -> None:
    """Duration of the ``validate_plan`` phase inside the weekly pipeline."""
    h = _histogram("weekchef.validate.duration_ms", "ms", "validate_plan phase duration")
    h.record(duration_ms, {})


def inc_llm_unavailable(*, step: str, reason: str) -> None:
    """``LLMUnavailableError`` or equivalent terminal failure (see reason labels)."""
    c = _counter("weekchef.llm.unavailable", "LLM unavailable / terminal completion failures")
    c.add(
        1,
        {
            "weekchef.step": step[:64],
            "reason": _norm_reason(reason)[:48],
        },
    )


def inc_llm_fallback_model(*, step: str) -> None:
    """One HTTP completion using the secondary model in the configured chain."""
    c = _counter("weekchef.llm.fallback_model_calls", "LLM calls using fallback model")
    c.add(1, {"weekchef.step": step[:64]})


def record_get_recipes_ms(duration_ms: float, *, tool_result: str, code: str = "") -> None:
    h = _histogram("weekchef.get_recipes.duration_ms", "ms", "get_recipes retriever latency")
    h.record(duration_ms, {"result": tool_result, "code": (code or "ok")[:32]})


def inc_get_recipes_result(*, tool_result: str, code: str = "") -> None:
    c = _counter("weekchef.get_recipes.calls", "get_recipes invocations")
    c.add(1, {"result": tool_result, "code": (code or "ok")[:32]})
