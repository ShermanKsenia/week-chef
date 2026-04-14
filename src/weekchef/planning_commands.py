"""Shared sync helpers for plan/replan/shopping/inventory/calendar (DB + orchestrator)."""

from __future__ import annotations

import json
import os
import random
import uuid
import re
from pathlib import Path
from typing import Any

from weekchef.calendar.oauth import credentials_from_db, refresh_and_persist_if_needed
from weekchef.config import get_settings
from weekchef.db.inventory import inventory_list, inventory_upsert
from weekchef.db.pool import sync_connection
from weekchef.db.sessions import session_get, session_upsert
from weekchef.orchestrator import build_shopping_for_plan, replan_week
from weekchef.observability import prepare_turn_patch, request_context
from weekchef.observability.dialogue import OBS_DIALOGUE_ID, OBS_TURN_INDEX
from weekchef.orchestrator_turn import process_user_turn
from weekchef.profile import load_or_seed_profile, telegram_user_key
from weekchef.schemas import ReplanTrigger, WeeklyPlan
from weekchef.shopping.parse_ingredients import normalize_product_name
from weekchef.tools.calendar import calendar_insert_events, cook_events_from_weekly_plan
from weekchef.tools.validate_plan import validate_plan

DEFAULT_PLAN_INTAKE_MESSAGE = (
    "Plan my meals for the week based on my saved profile and preferences."
)

_UNIT_SUFFIX = re.compile(
    r"^(.+?)\s+([\d.,]+)\s*(g|kg|ml|l|pcs|шт|шт\.|cup|cups|tbsp|tsp)$",
    re.IGNORECASE | re.UNICODE,
)


def profile_seed_path() -> Path:
    raw = os.environ.get("WEEKCHEF_PROFILE_PATH", "fixtures/profile.json")
    return Path(raw)


def merge_session_state(st: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Shallow merge for flat ``weekchef_sessions.state_json`` updates."""
    return {**st, **patch}


def plan_via_orchestrator_sync(telegram_user_id: int) -> tuple[bytes | None, bool | None, str]:
    """
    Same path as NL ``process_user_turn``: pipeline + shopping + session keys.

    Returns ``(plan_json_bytes, last_plan_valid, text_only_reply)``.
    If the orchestrator returns questions or no plan artifact, ``bytes`` is ``None``
    and ``text_only_reply`` is the user-facing message.
    """
    settings = get_settings()
    correlation_id = str(uuid.uuid4())
    with sync_connection(settings.database_url) as conn:
        st = session_get(conn, telegram_user_id)
        obs_patch = prepare_turn_patch(st)
        st2 = merge_session_state(st, obs_patch)
        if telegram_user_id:
            session_upsert(conn, telegram_user_id, st2)
        uk = telegram_user_key(telegram_user_id)
        with request_context(
            correlation_id=correlation_id,
            user_key=uk,
            dialogue_id=str(st2.get(OBS_DIALOGUE_ID) or ""),
            turn_index=int(st2.get(OBS_TURN_INDEX) or 0),
        ):
            resp = process_user_turn(conn, telegram_user_id, DEFAULT_PLAN_INTAKE_MESSAGE, st2)
        merged = merge_session_state(st2, resp.session_patch)
        if telegram_user_id:
            session_upsert(conn, telegram_user_id, merged)
        if resp.optional_plan is not None:
            data = json.dumps(
                json.loads(resp.optional_plan.model_dump_json()),
                indent=2,
                ensure_ascii=False,
            ).encode("utf-8")
            ok = bool(merged.get("last_plan_valid"))
            return data, ok, ""
        return None, None, resp.reply


def replan_sync(telegram_user_id: int) -> tuple[bytes, bool]:
    settings = get_settings()
    rng = random.Random()
    key = telegram_user_key(telegram_user_id)
    with sync_connection(settings.database_url) as conn:
        profile = load_or_seed_profile(conn, key, profile_seed_path())
        st = session_get(conn, telegram_user_id)
        raw_plan = st.get("last_plan")
        if not raw_plan:
            raise ValueError("No saved plan. Run /plan first.")
        plan = WeeklyPlan.model_validate(raw_plan)
        trigger = ReplanTrigger(trigger="calendar_change", affected_dates=[])
        new_plan = replan_week(conn, profile, settings, plan, trigger, rng=rng)
        v = validate_plan(new_plan, profile, conn, settings)
        new_plan.meta.reason_codes.extend(v.reason_codes)
        session_upsert(
            conn,
            telegram_user_id,
            {
                **st,
                "last_plan_valid": v.valid,
                "last_plan": json.loads(new_plan.model_dump_json()),
                "pending_calendar_events": cook_events_from_weekly_plan(new_plan)
                if settings.google_calendar_enabled
                else [],
            },
        )
        data = json.dumps(
            json.loads(new_plan.model_dump_json()),
            indent=2,
            ensure_ascii=False,
        ).encode("utf-8")
        return data, v.valid


def shopping_text_sync(telegram_user_id: int) -> str:
    settings = get_settings()
    key = telegram_user_key(telegram_user_id)
    with sync_connection(settings.database_url) as conn:
        st = session_get(conn, telegram_user_id)
        raw_plan = st.get("last_plan")
        if not raw_plan:
            return "No saved plan. Run /plan first."
        plan = WeeklyPlan.model_validate(raw_plan)
        profile = load_or_seed_profile(conn, key, profile_seed_path())
        shop = build_shopping_for_plan(conn, profile, settings, plan)
        if shop.error:
            return f"Shopping list failed: {shop.error}"
        if not shop.lines:
            return "Shopping list is empty."
        lines_out = []
        for ln in shop.lines:
            tag = " (have)" if ln.already_have else ""
            q = f"{ln.qty:g} {ln.unit}".strip() if ln.qty is not None else (ln.unit or "")
            lines_out.append(f"- {ln.product}: {q}{tag}".strip())
        return "Shopping list:\n" + "\n".join(lines_out)


def inventory_list_sync(telegram_user_id: int) -> str:
    settings = get_settings()
    key = telegram_user_key(telegram_user_id)
    with sync_connection(settings.database_url) as conn:
        rows = inventory_list(conn, key)
    if not rows:
        return "Pantry is empty. Add: /inventory_add flour 1 kg"
    lines = []
    for r in rows:
        q = r.get("qty")
        u = r.get("unit") or ""
        name = r.get("name_normalized") or ""
        if q is not None:
            lines.append(f"- {name}: {q:g} {u}".strip())
        else:
            lines.append(f"- {name}")
    return "Pantry:\n" + "\n".join(lines)


def inventory_add_sync(telegram_user_id: int, arg_line: str) -> str:
    s = (arg_line or "").strip()
    if not s:
        return "Usage: /inventory_add flour 1 kg"
    m = _UNIT_SUFFIX.match(s)
    if m:
        display_name = m.group(1).strip()
        qty = float(m.group(2).replace(",", "."))
        unit = m.group(3)
    else:
        parts = s.split()
        if len(parts) >= 2:
            try:
                qty = float(parts[-1].replace(",", "."))
                display_name = " ".join(parts[:-1])
                unit = ""
            except ValueError:
                display_name = s
                qty = None
                unit = None
        else:
            display_name = s
            qty = None
            unit = None
    nk = normalize_product_name(display_name)
    if not nk:
        return "Name is empty."
    settings = get_settings()
    key = telegram_user_key(telegram_user_id)
    with sync_connection(settings.database_url) as conn:
        inventory_upsert(conn, key, nk, qty, unit)
    qstr = f"{qty:g} {unit}".strip() if qty is not None else "ok"
    return f"Stored: {display_name} ({nk}) → {qstr}"


def confirm_calendar_sync(telegram_user_id: int) -> str:
    settings = get_settings()
    if not settings.google_calendar_enabled:
        return "Google Calendar writes are disabled (GOOGLE_CALENDAR_ENABLED)."
    key = telegram_user_key(telegram_user_id)
    with sync_connection(settings.database_url) as conn:
        st = session_get(conn, telegram_user_id)
        pending = st.get("pending_calendar_events") or []
        if not pending:
            return "No pending cook events. Run /plan first."
        profile = load_or_seed_profile(conn, key, profile_seed_path())
        creds = credentials_from_db(conn, profile.user_id, settings)
        if creds is None:
            return (
                "No Google OAuth token for this user. "
                "Run: python -m weekchef.google_oauth --user-key " + profile.user_id
            )
        creds = refresh_and_persist_if_needed(conn, profile.user_id, creds)
        ids, err = calendar_insert_events(creds, settings.google_calendar_id, pending)
        st2 = {**st, "pending_calendar_events": []}
        session_upsert(conn, telegram_user_id, st2)
    if err:
        return f"Partial: created {len(ids)} events; error: {err}"
    return f"Created {len(ids)} calendar events."
