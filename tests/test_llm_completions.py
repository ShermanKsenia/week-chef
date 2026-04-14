"""Structured LLM completions (mocked OpenAI client, no network)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel
from pydantic_settings import SettingsConfigDict

from weekchef.config import Settings
from weekchef.llm.completions import complete_json_sync
from weekchef.llm.outputs import ParseInputResult
from weekchef.llm.parse_input import run_parse_input_sync


class _SettingsNoEnvFile(Settings):
    model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


class _Tiny(BaseModel):
    x: int = 1


def _fake_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
    )


def test_complete_json_sync_parses_model() -> None:
    s = _SettingsNoEnvFile(
        llm_api_key="k",
        llm_model="m1",
        llm_fallback_model="",
        llm_max_retries=1,
        llm_max_json_retries=2,
    )
    client = MagicMock()
    client.chat.completions.create.return_value = _fake_response('{"x": 2}')
    out = complete_json_sync(
        [{"role": "user", "content": "hi"}],
        _Tiny,
        settings=s,
        client=client,
    )
    assert out.x == 2
    client.chat.completions.create.assert_called()
    call_kw = client.chat.completions.create.call_args.kwargs
    assert call_kw["model"] == "m1"
    assert call_kw["response_format"] == {"type": "json_object"}


def test_fallback_model_used_after_transport_error() -> None:
    try:
        from openai import APIConnectionError
    except ImportError:
        pytest.skip("openai not installed")

    s = _SettingsNoEnvFile(
        llm_api_key="k",
        llm_model="primary",
        llm_fallback_model="fallback",
        llm_max_retries=1,
        llm_max_json_retries=1,
    )
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        APIConnectionError(request=MagicMock()),
        _fake_response('{"x": 7}'),
    ]
    out = complete_json_sync(
        [{"role": "user", "content": "hi"}],
        _Tiny,
        settings=s,
        client=client,
    )
    assert out.x == 7
    models = [c.kwargs["model"] for c in client.chat.completions.create.call_args_list]
    assert models == ["primary", "fallback"]


def test_run_parse_input_sync_mocked() -> None:
    s = _SettingsNoEnvFile(
        llm_api_key="k",
        llm_max_retries=1,
        llm_max_json_retries=1,
    )
    payload = ParseInputResult(
        intent_summary="test",
        servings=2,
        meals_per_day=3,
        dietary_notes=["veg"],
        allergies_or_bans=[],
        week_start_iso=None,
        missing_required_fields=[],
    )
    client = MagicMock()
    client.chat.completions.create.return_value = _fake_response(payload.model_dump_json())
    out = run_parse_input_sync("I need vegetarian meals", settings=s, client=client)
    assert out.intent_summary == "test"
    assert out.servings == 2
