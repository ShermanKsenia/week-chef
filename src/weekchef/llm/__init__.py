"""LLM access via OpenAI SDK (OpenRouter-compatible)."""

from weekchef.llm.client import (
    build_async_openai_client,
    build_sync_openai_client,
    effective_llm_base_url,
)

__all__ = [
    "build_async_openai_client",
    "build_sync_openai_client",
    "effective_llm_base_url",
]
