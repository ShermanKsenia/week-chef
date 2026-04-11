"""Thin OpenAI SDK clients for OpenRouter (OpenAI-compatible API)."""

from __future__ import annotations

from typing import Any

from weekchef.config import Settings, get_settings


def effective_llm_base_url(settings: Settings) -> str:
    return settings.effective_llm_base_url()


def _optional_default_headers(settings: Settings) -> dict[str, str] | None:
    h: dict[str, str] = {}
    if settings.openrouter_http_referer:
        h["HTTP-Referer"] = settings.openrouter_http_referer
    if settings.openrouter_app_title:
        h["X-Title"] = settings.openrouter_app_title
    return h or None


def _shared_kwargs(settings: Settings) -> dict[str, Any]:
    kw: dict[str, Any] = {"base_url": effective_llm_base_url(settings)}
    headers = _optional_default_headers(settings)
    if headers:
        kw["default_headers"] = headers
    return kw


def build_sync_openai_client(
    settings: Settings | None = None,
    *,
    require_api_key: bool = True,
) -> Any:
    """Synchronous OpenAI client (CLI / blocking orchestrator paths)."""
    from openai import OpenAI

    s = settings or get_settings()
    key = (s.llm_api_key or "").strip()
    if require_api_key and not key:
        msg = "Set OPENROUTER_API_KEY or LLM_API_KEY for LLM calls."
        raise ValueError(msg)
    kw = _shared_kwargs(s)
    kw["api_key"] = key or "sk-or-v1-placeholder"
    return OpenAI(**kw)


def build_async_openai_client(
    settings: Settings | None = None,
    *,
    require_api_key: bool = True,
) -> Any:
    """Async OpenAI client (aiogram / async orchestrator)."""
    from openai import AsyncOpenAI

    s = settings or get_settings()
    key = (s.llm_api_key or "").strip()
    if require_api_key and not key:
        msg = "Set OPENROUTER_API_KEY or LLM_API_KEY for LLM calls."
        raise ValueError(msg)
    kw = _shared_kwargs(s)
    kw["api_key"] = key or "sk-or-v1-placeholder"
    return AsyncOpenAI(**kw)
