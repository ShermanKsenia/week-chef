"""Aiogram command handlers."""

from __future__ import annotations

import asyncio
import uuid

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from weekchef.config import get_settings
from weekchef.db.pool import sync_connection
from weekchef.db.sessions import session_get, session_upsert
from weekchef.observability import prepare_turn_patch, request_context, reset_dialogue_state
from weekchef.observability.dialogue import OBS_DIALOGUE_ID, OBS_TURN_INDEX
from weekchef.orchestrator_turn import process_user_turn
from weekchef.profile import telegram_user_key
from weekchef.planning_commands import (
    confirm_calendar_sync,
    inventory_add_sync,
    inventory_list_sync,
    merge_session_state,
    plan_via_orchestrator_sync,
    replan_sync,
    shopping_text_sync,
)

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    uid = int(message.from_user.id) if message.from_user else 0
    if uid:

        def _reset_dialogue() -> None:
            settings = get_settings()
            with sync_connection(settings.database_url) as conn:
                st = session_get(conn, uid)
                session_upsert(conn, uid, merge_session_state(st, reset_dialogue_state()))

        await asyncio.to_thread(_reset_dialogue)
    await message.answer(
        "Week Chef PoC.\n"
        "Send a normal message to plan (or clarify) via the orchestrator.\n"
        "/plan — weekly plan JSON (same pipeline as chat)\n"
        "/replan — re-plan from last plan\n"
        "/shopping — shopping list from last plan\n"
        "/inventory — pantry list\n"
        "/inventory_add — add item (e.g. rice 1 kg)\n"
        "/confirm_calendar — write cook events (needs OAuth + calendar.events scope)\n"
        "/help — this text"
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await cmd_start(message)


@router.message(Command("plan"))
async def cmd_plan(message: Message) -> None:
    uid = int(message.from_user.id) if message.from_user else 0

    def _run() -> tuple[bytes | None, bool | None, str]:
        return plan_via_orchestrator_sync(uid)

    try:
        data, ok, text_only = await asyncio.to_thread(_run)
    except Exception as e:  # noqa: BLE001
        await message.answer(f"Plan failed: {e}")
        return
    settings = get_settings()
    if data is not None:
        cap = "plan.json"
        doc = BufferedInputFile(data, filename=cap)
        extra = ""
        if settings.google_calendar_enabled:
            extra = " Use /confirm_calendar to write cook slots to Google Calendar."
        await message.answer_document(document=doc, caption=f"valid={ok}.{extra}")
    else:
        await message.answer((text_only or "No plan produced.")[:4000])


@router.message(Command("replan"))
async def cmd_replan(message: Message) -> None:
    uid = int(message.from_user.id) if message.from_user else 0
    try:
        data, ok = await asyncio.to_thread(replan_sync, uid)
    except Exception as e:  # noqa: BLE001
        await message.answer(f"Replan failed: {e}")
        return
    doc = BufferedInputFile(data, filename="plan.json")
    await message.answer_document(document=doc, caption=f"valid={ok}")


@router.message(Command("shopping"))
async def cmd_shopping(message: Message) -> None:
    uid = int(message.from_user.id) if message.from_user else 0
    try:
        text = await asyncio.to_thread(shopping_text_sync, uid)
    except Exception as e:  # noqa: BLE001
        await message.answer(f"Shopping failed: {e}")
        return
    await message.answer(text[:4000])


@router.message(Command("inventory"))
async def cmd_inventory(message: Message) -> None:
    uid = int(message.from_user.id) if message.from_user else 0
    text = await asyncio.to_thread(inventory_list_sync, uid)
    await message.answer(text[:4000])


@router.message(Command("inventory_add"))
async def cmd_inventory_add(message: Message) -> None:
    uid = int(message.from_user.id) if message.from_user else 0
    raw = message.text or ""
    arg_line = raw.split(maxsplit=1)[1] if len(raw.split(maxsplit=1)) > 1 else ""
    text = await asyncio.to_thread(inventory_add_sync, uid, arg_line)
    await message.answer(text[:4000])


@router.message(Command("confirm_calendar"))
async def cmd_confirm_calendar(message: Message) -> None:
    uid = int(message.from_user.id) if message.from_user else 0
    text = await asyncio.to_thread(confirm_calendar_sync, uid)
    await message.answer(text[:4000])


@router.message(F.text, ~F.text.startswith("/"))
async def nl_user_turn(message: Message) -> None:
    """Free-text entry: same orchestrator facade as other UIs (no slash command)."""
    uid = int(message.from_user.id) if message.from_user else 0
    body = (message.text or "").strip()
    if not body:
        return

    def _run() -> str:
        settings = get_settings()
        correlation_id = str(uuid.uuid4())
        with sync_connection(settings.database_url) as conn:
            st = session_get(conn, uid)
            obs_patch = prepare_turn_patch(st)
            st2 = merge_session_state(st, obs_patch)
            if uid:
                session_upsert(conn, uid, st2)
            uk = telegram_user_key(uid)
            with request_context(
                correlation_id=correlation_id,
                user_key=uk,
                dialogue_id=str(st2.get(OBS_DIALOGUE_ID) or ""),
                turn_index=int(st2.get(OBS_TURN_INDEX) or 0),
            ):
                resp = process_user_turn(conn, uid, body, st2)
                merged = merge_session_state(st2, resp.session_patch)
                if uid:
                    session_upsert(conn, uid, merged)
                return resp.reply

    try:
        reply = await asyncio.to_thread(_run)
    except Exception as e:  # noqa: BLE001
        await message.answer(f"Request failed: {e}")
        return
    await message.answer(reply[:4000])
