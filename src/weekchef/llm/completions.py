"""JSON structured completions with retries and fallback model."""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from weekchef.config import Settings, get_settings
from weekchef.llm.client import build_async_openai_client, build_sync_openai_client
from weekchef.llm.langfuse_util import flush_langfuse, langfuse_completion_extras
from weekchef.llm.errors import LLMInvalidResponseError, LLMUnavailableError
from weekchef.observability.context import otel_common_attributes
from weekchef.observability.metrics import (
    inc_llm_completion,
    inc_llm_fallback_model,
    inc_llm_json_retry,
    inc_llm_unavailable,
)
from weekchef.observability.otel import get_tracer

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)


def _strip_json_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = _FENCE_RE.sub("", t)
        if t.endswith("```"):
            t = t[: -3].strip()
    return t.strip()


def _is_retryable_transport(exc: BaseException) -> bool:
    try:
        from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
    except ImportError:
        return False
    if isinstance(exc, (APITimeoutError, APIConnectionError, RateLimitError)):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code in (408, 409, 429, 500, 502, 503, 504)
    return False


def _is_nonrecoverable(exc: BaseException) -> bool:
    try:
        from openai import APIStatusError, AuthenticationError, BadRequestError
    except ImportError:
        return False
    if isinstance(exc, (AuthenticationError, BadRequestError)):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code in (400, 401, 403, 404):
        return True
    return False


def _model_chain(settings: Settings) -> list[str]:
    primary = (settings.llm_model or "").strip() or "openai/gpt-4o-mini"
    fb = (settings.llm_fallback_model or "").strip()
    out = [primary]
    if fb and fb != primary:
        out.append(fb)
    return out


def _parse_response_content(content: str | None) -> str:
    if content is None or not str(content).strip():
        raise LLMInvalidResponseError("empty model content")
    return _strip_json_fences(str(content))


def llm_unavailable_after_schema_retries(exc: LLMUnavailableError) -> bool:
    """True when ``complete_json_*`` exhausted JSON/schema retries (vs transport/auth outage)."""
    if "failed after retries" not in str(exc).lower():
        return False
    return any(isinstance(c, (ValidationError, json.JSONDecodeError)) for c in (exc.causes or []))


def _validation_feedback_for_retry(exc: BaseException) -> str:
    """Compact feedback for the model on the next attempt (avoids huge str(ValidationError))."""
    if isinstance(exc, ValidationError):
        try:
            return json.dumps(exc.errors()[:16], ensure_ascii=False, default=str)[:1200]
        except Exception:
            return f"{type(exc).__name__}"[:1200]
    return str(exc)[:1200]


def _maybe_log_invalid_json_output(
    settings: Settings,
    *,
    step: str,
    raw: str,
    exc: BaseException,
) -> None:
    """Log a truncated raw model string when enabled (see governance: may echo user content)."""
    n = max(0, int(settings.llm_validation_preview_chars))
    if n <= 0:
        return
    from weekchef.observability.logging_setup import get_logger

    log = get_logger("weekchef.llm")
    preview = (raw or "")[:n].replace("\n", "\\n")
    log.warning(
        "llm_json_validation_failed",
        step=step,
        preview=preview,
        error_type=type(exc).__name__,
        raw_chars=len(raw or ""),
    )


def _one_sync_completion(
    c: Any,
    *,
    settings: Settings,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout: float,
    llm_step: str,
    prompt_version: str | None,
) -> str:
    tracer = get_tracer("weekchef.llm")
    attrs = {
        **otel_common_attributes(),
        "gen_ai.request.model": model,
        "weekchef.step": llm_step,
    }
    if prompt_version:
        attrs["weekchef.prompt_version"] = prompt_version
    lf_kw = langfuse_completion_extras(settings, llm_step=llm_step, prompt_version=prompt_version)
    with tracer.start_as_current_span("llm.completion", attributes=attrs) as span:
        try:
            resp = c.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                timeout=timeout,
                **lf_kw,
            )
            usage = getattr(resp, "usage", None)
            if usage is not None:
                pt = getattr(usage, "prompt_tokens", None)
                ct = getattr(usage, "completion_tokens", None)
                if pt is not None:
                    span.set_attribute("gen_ai.usage.prompt_tokens", int(pt))
                if ct is not None:
                    span.set_attribute("gen_ai.usage.completion_tokens", int(ct))
            raw = _parse_response_content(resp.choices[0].message.content)
            span.set_attribute("weekchef.result", "ok")
            inc_llm_completion(step=llm_step, result="ok", model=model)
            return raw
        except Exception as e:  # noqa: BLE001
            span.set_attribute("error", True)
            span.set_attribute("weekchef.error_code", type(e).__name__)
            inc_llm_completion(step=llm_step, result="error", model=model)
            raise


async def _one_async_completion(
    c: Any,
    *,
    settings: Settings,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout: float,
    llm_step: str,
    prompt_version: str | None,
) -> str:
    tracer = get_tracer("weekchef.llm")
    attrs = {
        **otel_common_attributes(),
        "gen_ai.request.model": model,
        "weekchef.step": llm_step,
    }
    if prompt_version:
        attrs["weekchef.prompt_version"] = prompt_version
    lf_kw = langfuse_completion_extras(settings, llm_step=llm_step, prompt_version=prompt_version)
    with tracer.start_as_current_span("llm.completion", attributes=attrs) as span:
        try:
            resp = await c.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                timeout=timeout,
                **lf_kw,
            )
            usage = getattr(resp, "usage", None)
            if usage is not None:
                pt = getattr(usage, "prompt_tokens", None)
                ct = getattr(usage, "completion_tokens", None)
                if pt is not None:
                    span.set_attribute("gen_ai.usage.prompt_tokens", int(pt))
                if ct is not None:
                    span.set_attribute("gen_ai.usage.completion_tokens", int(ct))
            raw = _parse_response_content(resp.choices[0].message.content)
            span.set_attribute("weekchef.result", "ok")
            inc_llm_completion(step=llm_step, result="ok", model=model)
            return raw
        except Exception as e:  # noqa: BLE001
            span.set_attribute("error", True)
            span.set_attribute("weekchef.error_code", type(e).__name__)
            inc_llm_completion(step=llm_step, result="error", model=model)
            raise


def complete_json_sync(
    messages: list[dict[str, str]],
    response_model: type[T],
    *,
    settings: Settings | None = None,
    client: Any | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    llm_step: str | None = None,
    prompt_version: str | None = None,
) -> T:
    """Synchronous chat completion that returns a validated Pydantic model."""
    s = settings or get_settings()
    c = client or build_sync_openai_client(s)
    max_json_attempts = max(1, s.llm_max_json_retries)
    transport_retries = max(1, s.llm_max_retries)
    timeout = float(s.llm_timeout_seconds)
    causes: list[BaseException] = []
    feedback: str | None = None
    step = llm_step or "llm.json_completion"
    model_chain = _model_chain(s)
    primary_model = model_chain[0]

    try:
        for _json_attempt in range(max_json_attempts):
            msgs: list[dict[str, str]] = list(messages)
            if feedback:
                msgs = msgs + [
                    {"role": "user", "content": f"Fix your previous reply. Issue: {feedback[:1200]}"},
                ]

            transport_failed = False
            for model in model_chain:
                for _ in range(transport_retries):
                    try:
                        if model != primary_model:
                            inc_llm_fallback_model(step=step)
                        raw = _one_sync_completion(
                            c,
                            settings=s,
                            model=model,
                            messages=msgs,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            timeout=timeout,
                            llm_step=step,
                            prompt_version=prompt_version,
                        )
                        try:
                            return response_model.model_validate_json(raw)
                        except (ValidationError, json.JSONDecodeError) as e:
                            _maybe_log_invalid_json_output(s, step=step, raw=raw, exc=e)
                            causes.append(e)
                            feedback = _validation_feedback_for_retry(e)
                            transport_failed = False
                            inc_llm_json_retry(step)
                            break
                    except LLMInvalidResponseError as e:
                        causes.append(e)
                        feedback = _validation_feedback_for_retry(e)
                        transport_failed = False
                        inc_llm_json_retry(step)
                        break
                    except Exception as e:  # noqa: BLE001
                        causes.append(e)
                        if _is_nonrecoverable(e):
                            inc_llm_unavailable(step=step, reason="nonrecoverable")
                            raise LLMUnavailableError(str(e), causes=[e]) from e
                        if _is_retryable_transport(e):
                            transport_failed = True
                            continue
                        raise

                if feedback is not None:
                    break

            if feedback is not None:
                continue

            if transport_failed:
                continue

        exc = LLMUnavailableError("LLM structured completion failed after retries", causes=causes)
        reason = "schema_retries_exhausted" if llm_unavailable_after_schema_retries(exc) else "transport_retries_exhausted"
        inc_llm_unavailable(step=step, reason=reason)
        raise exc
    finally:
        flush_langfuse(s)


async def complete_json_async(
    messages: list[dict[str, str]],
    response_model: type[T],
    *,
    settings: Settings | None = None,
    client: Any | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    llm_step: str | None = None,
    prompt_version: str | None = None,
) -> T:
    """Async chat completion that returns a validated Pydantic model."""
    s = settings or get_settings()
    c = client or build_async_openai_client(s)
    max_json_attempts = max(1, s.llm_max_json_retries)
    transport_retries = max(1, s.llm_max_retries)
    timeout = float(s.llm_timeout_seconds)
    causes: list[BaseException] = []
    feedback: str | None = None
    step = llm_step or "llm.json_completion"
    model_chain = _model_chain(s)
    primary_model = model_chain[0]

    try:
        for _json_attempt in range(max_json_attempts):
            msgs: list[dict[str, str]] = list(messages)
            if feedback:
                msgs = msgs + [
                    {"role": "user", "content": f"Fix your previous reply. Issue: {feedback[:1200]}"},
                ]

            transport_failed = False
            for model in model_chain:
                for _ in range(transport_retries):
                    try:
                        if model != primary_model:
                            inc_llm_fallback_model(step=step)
                        raw = await _one_async_completion(
                            c,
                            settings=s,
                            model=model,
                            messages=msgs,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            timeout=timeout,
                            llm_step=step,
                            prompt_version=prompt_version,
                        )
                        try:
                            return response_model.model_validate_json(raw)
                        except (ValidationError, json.JSONDecodeError) as e:
                            _maybe_log_invalid_json_output(s, step=step, raw=raw, exc=e)
                            causes.append(e)
                            feedback = _validation_feedback_for_retry(e)
                            transport_failed = False
                            inc_llm_json_retry(step)
                            break
                    except LLMInvalidResponseError as e:
                        causes.append(e)
                        feedback = _validation_feedback_for_retry(e)
                        transport_failed = False
                        inc_llm_json_retry(step)
                        break
                    except Exception as e:  # noqa: BLE001
                        causes.append(e)
                        if _is_nonrecoverable(e):
                            inc_llm_unavailable(step=step, reason="nonrecoverable")
                            raise LLMUnavailableError(str(e), causes=[e]) from e
                        if _is_retryable_transport(e):
                            transport_failed = True
                            continue
                        raise

                if feedback is not None:
                    break

            if feedback is not None:
                continue

            if transport_failed:
                continue

        exc = LLMUnavailableError("LLM structured completion failed after retries", causes=causes)
        reason = "schema_retries_exhausted" if llm_unavailable_after_schema_retries(exc) else "transport_retries_exhausted"
        inc_llm_unavailable(step=step, reason=reason)
        raise exc
    finally:
        flush_langfuse(s)
