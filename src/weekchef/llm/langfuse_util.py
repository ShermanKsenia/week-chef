"""Langfuse client bootstrap and flush (optional dependency)."""

from __future__ import annotations

from typing import Any

from weekchef.config import Settings, get_settings


def langfuse_client_configured(settings: Settings) -> bool:
    return bool(
        settings.langfuse_tracing_enabled
        and settings.langfuse_public_key.strip()
        and settings.langfuse_secret_key.strip()
    )


def ensure_langfuse_client(settings: Settings) -> None:
    """Register a Langfuse SDK client for this project's public key (idempotent per process)."""
    if not langfuse_client_configured(settings):
        return
    from langfuse import Langfuse

    pk = settings.langfuse_public_key.strip()
    sk = settings.langfuse_secret_key.strip()
    host = settings.langfuse_host.strip() or None
    Langfuse(public_key=pk, secret_key=sk, host=host)


def flush_langfuse(settings: Settings | None = None) -> None:
    """Best-effort flush of buffered Langfuse observations (CLI / short-lived workers)."""
    s = settings or get_settings()
    if not langfuse_client_configured(s):
        return
    try:
        from langfuse import get_client
    except ImportError:
        return
    try:
        pk = s.langfuse_public_key.strip()
        get_client(public_key=pk).flush()
    except Exception:
        return


def langfuse_completion_extras(
    settings: Settings,
    *,
    llm_step: str,
    prompt_version: str | None,
) -> dict[str, Any]:
    """Kwargs for ``chat.completions.create`` consumed by Langfuse OpenAI wrapper (no ``session_id`` — use metadata)."""
    if not langfuse_client_configured(settings):
        return {}
    from weekchef.observability.context import get_correlation_id, get_dialogue_id, get_user_key

    meta: dict[str, str] = {}
    cid = get_correlation_id()
    if cid:
        meta["weekchef.correlation_id"] = cid
    did = get_dialogue_id()
    if did:
        meta["weekchef.dialogue_id"] = did
    uk = get_user_key()
    if uk:
        meta["weekchef.user_id"] = uk
    if prompt_version:
        meta["weekchef.prompt_version"] = str(prompt_version)
    pk = settings.langfuse_public_key.strip()
    return {
        "name": llm_step,
        "langfuse_public_key": pk,
        "metadata": meta,
    }
