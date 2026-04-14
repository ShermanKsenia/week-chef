"""Schema-retry exhaustion vs generic LLMUnavailableError."""

from __future__ import annotations

import json

from pydantic import BaseModel, ValidationError

from weekchef.llm.completions import llm_unavailable_after_schema_retries
from weekchef.llm.errors import LLMUnavailableError


class _M(BaseModel):
    x: int


def test_llm_unavailable_after_schema_retries_true():
    try:
        _M.model_validate_json("{}")
    except ValidationError as ve:
        exc = LLMUnavailableError("LLM structured completion failed after retries", causes=[ve])
    assert llm_unavailable_after_schema_retries(exc) is True


def test_llm_unavailable_after_schema_retries_json_decode():
    err = json.JSONDecodeError("msg", "doc", 0)
    exc = LLMUnavailableError("LLM structured completion failed after retries", causes=[err])
    assert llm_unavailable_after_schema_retries(exc) is True


def test_llm_unavailable_after_schema_retries_false_wrong_message():
    exc = LLMUnavailableError("connection reset", causes=[ValueError("x")])
    assert llm_unavailable_after_schema_retries(exc) is False


def test_llm_unavailable_after_schema_retries_false_transport_only():
    exc = LLMUnavailableError("LLM structured completion failed after retries", causes=[ValueError("x")])
    assert llm_unavailable_after_schema_retries(exc) is False
