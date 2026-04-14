"""LLM client configuration (no live API calls)."""

import pytest

from weekchef.config import DEFAULT_OPENROUTER_BASE_URL, Settings
from weekchef.llm.client import build_async_openai_client, build_sync_openai_client, effective_llm_base_url


def test_effective_llm_base_url_default() -> None:
    s = Settings(llm_base_url="")
    assert effective_llm_base_url(s) == DEFAULT_OPENROUTER_BASE_URL


def test_effective_llm_base_url_custom() -> None:
    s = Settings(llm_base_url="https://example.com/v1")
    assert effective_llm_base_url(s) == "https://example.com/v1"


def test_build_sync_requires_key() -> None:
    s = Settings(llm_api_key="")
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        build_sync_openai_client(s, require_api_key=True)


def test_build_sync_without_key_for_import_tests() -> None:
    s = Settings(llm_api_key="")
    client = build_sync_openai_client(s, require_api_key=False)
    assert "openrouter.ai" in str(client.base_url)


def test_openrouter_headers_optional() -> None:
    s = Settings(
        llm_api_key="x",
        openrouter_http_referer="https://example.com",
        openrouter_app_title="Test",
    )
    c = build_sync_openai_client(s)
    assert c is not None


@pytest.mark.asyncio
async def test_build_async_without_key() -> None:
    s = Settings(llm_api_key="")
    client = build_async_openai_client(s, require_api_key=False)
    assert client is not None
