"""Run Telegram bot (long polling)."""

from __future__ import annotations

import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from weekchef.config import get_settings
from weekchef.observability import configure_observability
from weekchef.telegram.handlers import router
from weekchef.telegram.http_proxy_session import AiohttpHttpProxySession


def _normalize_proxy_url(raw: str) -> str:
    s = raw.strip()
    if "://" not in s:
        return f"http://{s}"
    return s


def _make_bot_session(proxy: str | None, timeout: float):
    """
    - No proxy: default aiohttp session.
    - ``http(s)://``: native aiohttp proxy (no aiohttp-socks).
    - ``socks*://``: aiogram's session (requires ``pip install aiohttp-socks``).
    """
    if not proxy:
        return AiohttpSession(timeout=timeout)
    url = _normalize_proxy_url(proxy)
    lower = url.lower()
    scheme = lower.split("://", 1)[0] if "://" in lower else ""
    if scheme.startswith("socks"):
        return AiohttpSession(proxy=url, timeout=timeout)
    if lower.startswith(("http://", "https://")):
        return AiohttpHttpProxySession(url, timeout=timeout)
    return AiohttpHttpProxySession(url, timeout=timeout)


async def _amain() -> None:
    settings = get_settings()
    configure_observability(settings)
    token = settings.telegram_bot_token.strip()
    if not token:
        print("Set TELEGRAM_BOT_TOKEN in the environment.", file=sys.stderr)
        raise SystemExit(1)
    proxy = settings.telegram_proxy_url.strip() or None
    session = _make_bot_session(proxy, settings.telegram_api_timeout_seconds)
    bot = Bot(token, session=session)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
