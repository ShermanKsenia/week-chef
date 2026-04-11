"""Run Telegram bot (long polling)."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher

from weekchef.config import get_settings
from weekchef.telegram.handlers import router


async def _amain() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    token = settings.telegram_bot_token.strip()
    if not token:
        print("Set TELEGRAM_BOT_TOKEN in the environment.", file=sys.stderr)
        raise SystemExit(1)
    bot = Bot(token)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
