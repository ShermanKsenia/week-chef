"""LLM client configuration (no live API calls)."""

import pytest
from pydantic_settings import SettingsConfigDict

from weekchef.config import DEFAULT_OPENROUTER_BASE_URL, Settings
from weekchef.llm.client import build_async_openai_client, build_sync_openai_client, effective_llm_base_url


class _SettingsNoEnvFile(Settings):
    """Same as Settings but do not read `.env` (tests must not depend on local secrets)."""

    model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


def test_effective_llm_base_url_default() -> None:
    s = Settings(llm_base_url="")
    assert effective_llm_base_url(s) == DEFAULT_OPENROUTER_BASE_URL


def test_effective_llm_base_url_custom() -> None:
    s = Settings(llm_base_url="https://example.com/v1")
    assert effective_llm_base_url(s) == "https://example.com/v1"


def test_build_sync_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    s = _SettingsNoEnvFile(llm_api_key="")
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY|LLM_API_KEY"):
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


def test_build_sync_uses_openai_module_when_langfuse_disabled() -> None:
    s = _SettingsNoEnvFile(llm_api_key="sk-x", langfuse_tracing_enabled=False)
    c = build_sync_openai_client(s)
    assert type(c).__module__.startswith("openai")


def test_build_async_uses_openai_module_when_langfuse_disabled() -> None:
    s = _SettingsNoEnvFile(llm_api_key="sk-x", langfuse_tracing_enabled=False)
    c = build_async_openai_client(s)
    assert type(c).__module__.startswith("openai")


def test_build_sync_langfuse_flag_without_keys_uses_openai() -> None:
    """Tracing wrapper requires both Langfuse keys; otherwise stay on vanilla OpenAI."""
    s = _SettingsNoEnvFile(
        llm_api_key="sk-x",
        langfuse_tracing_enabled=True,
        langfuse_public_key="",
        langfuse_secret_key="",
    )
    c = build_sync_openai_client(s)
    assert type(c).__module__.startswith("openai")


def test_build_sync_calls_ensure_langfuse_when_tracing_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``langfuse.openai`` patches the global ``openai.OpenAI`` class; we assert the Langfuse branch ran."""
    pytest.importorskip("langfuse.openai")
    called: list[int] = []

    def _spy(settings: object) -> None:
        called.append(1)

    monkeypatch.setattr("weekchef.llm.langfuse_util.ensure_langfuse_client", _spy)
    s = _SettingsNoEnvFile(
        llm_api_key="sk-or-test",
        langfuse_tracing_enabled=True,
        langfuse_public_key="pk-lf-test",
        langfuse_secret_key="sk-lf-test",
    )
    from langfuse import Langfuse

    Langfuse(public_key="pk-lf-test", secret_key="sk-lf-test", tracing_enabled=False)
    c = build_sync_openai_client(s)
    assert called == [1]
    assert c is not None
