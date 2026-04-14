"""Aiogram command handlers."""

from __future__ import annotations

import asyncio
import json
import os
import random
from pathlib import Path

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from weekchef.config import get_settings
from weekchef.db.pool import sync_connection
from weekchef.db.sessions import session_upsert
from weekchef.orchestrator import build_weekly_plan
from weekchef.profile import load_profile
from weekchef.tools.validate_plan import validate_plan

router = Router()


def _profile_path() -> Path:
    raw = os.environ.get("WEEKCHEF_PROFILE_PATH", "fixtures/profile.json")
    return Path(raw)


def _build_plan_sync(telegram_user_id: int) -> tuple[bytes, bool]:
    settings = get_settings()
    profile = load_profile(_profile_path())
    rng = random.Random()
    with sync_connection(settings.database_url) as conn:
        plan = build_weekly_plan(conn, profile, settings, rng=rng)
        result = validate_plan(plan, profile, conn, settings)
        plan.meta.reason_codes.extend(result.reason_codes)
        if telegram_user_id:
            session_upsert(
                conn,
                telegram_user_id,
                {"last_plan_valid": result.valid, "pipeline": settings.pipeline_version},
            )
        text = json.dumps(
            json.loads(plan.model_dump_json()),
            indent=2,
            ensure_ascii=False,
        ).encode("utf-8")
        return text, result.valid


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Week Chef PoC. Use /plan to generate a weekly plan JSON from the configured profile."
    )


@router.message(Command("plan"))
async def cmd_plan(message: Message) -> None:
    uid = int(message.from_user.id) if message.from_user else 0
    try:
        data, ok = await asyncio.to_thread(_build_plan_sync, uid)
    except Exception as e:  # noqa: BLE001
        await message.answer(f"Plan failed: {e}")
        return
    cap = "plan.json"
    doc = BufferedInputFile(data, filename=cap)
    await message.answer_document(document=doc, caption=f"valid={ok}")
