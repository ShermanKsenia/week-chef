"""Orchestrator: ENRICH (calendar) + planning pipeline."""

from __future__ import annotations

import random

from psycopg import Connection

from weekchef.calendar.oauth import credentials_from_db, refresh_and_persist_if_needed
from weekchef.calendar.slots import refine_slots_for_cooking
from weekchef.config import Settings
from weekchef.planner.calendar_assign import assign_meals_to_calendar_slots
from weekchef.planner.simple import plan_simple_week
from weekchef.replan.detect import dates_for_slot_ids, slot_ids_calendar_unassigned
from weekchef.replan.local import replan_affected_days
from weekchef.schemas import (
    CalendarFreeBusy,
    ReplanTrigger,
    ShoppingListResult,
    UserProfile,
    WeeklyPlan,
)
from weekchef.observability import get_logger
from weekchef.tools.calendar import calendar_free_busy_for_profile, synthetic_calendar_week
from weekchef.tools.shopping import build_shopping_list, recipe_ids_from_plan

_log = get_logger("weekchef.orchestrator")


def enrich_calendar(conn: Connection, profile: UserProfile, settings: Settings) -> CalendarFreeBusy:
    """
    ENRICH step: load free/busy for the profile week, or synthetic windows when Calendar is off.

    If Google Calendar is enabled globally but this user has no OAuth row yet, falls back to
    synthetic slots so planning (e.g. Streamlit) does not hard-fail; see log
    ``enrich_calendar_oauth_missing``.
    """
    if not settings.google_calendar_enabled:
        return synthetic_calendar_week(profile)

    creds = credentials_from_db(conn, profile.user_id, settings)
    if creds is None:
        _log.warning(
            "enrich_calendar_oauth_missing",
            user_key=profile.user_id,
            message="GOOGLE_CALENDAR_ENABLED but no token; using synthetic_calendar_week",
        )
        return synthetic_calendar_week(profile)

    creds = refresh_and_persist_if_needed(conn, profile.user_id, creds)
    raw = calendar_free_busy_for_profile(creds, settings.google_calendar_id, profile)
    return refine_slots_for_cooking(
        raw,
        profile,
        min_slot_minutes=settings.calendar_min_slot_minutes,
        max_slots_per_day=settings.calendar_max_slots_per_day,
    )


def build_weekly_plan(
    conn: Connection,
    profile: UserProfile,
    settings: Settings,
    *,
    rng: random.Random | None = None,
) -> WeeklyPlan:
    """Plan week, then align cook windows to calendar when `GOOGLE_CALENDAR_ENABLED`."""
    cal = enrich_calendar(conn, profile, settings)
    plan = plan_simple_week(profile, conn, settings, calendar=cal, rng=rng)
    if settings.google_calendar_enabled:
        plan, cal_reasons = assign_meals_to_calendar_slots(
            plan,
            cal,
            profile.timezone,
            profile.planning_defaults.prep_buffer_minutes,
        )
        plan.meta.reason_codes.extend(cal_reasons)
    return plan


def build_shopping_for_plan(
    conn: Connection,
    profile: UserProfile,
    settings: Settings,
    plan: WeeklyPlan,
    *,
    subtract_inventory: bool = True,
) -> ShoppingListResult:
    rids = recipe_ids_from_plan(plan)
    return build_shopping_list(
        conn,
        settings,
        rids,
        profile.servings,
        subtract_inventory=subtract_inventory,
        user_key=profile.user_id,
    )


def replan_week(
    conn: Connection,
    profile: UserProfile,
    settings: Settings,
    plan: WeeklyPlan,
    trigger: ReplanTrigger,
    *,
    rng: random.Random | None = None,
    max_calendar_passes: int = 3,
) -> WeeklyPlan:
    """
    Re-plan affected slots/days, then re-assign calendar windows when enabled.

    If slots still do not fit, retries with ``calendar_change`` on conflicting
    dates (up to ``max_calendar_passes`` total passes).
    """
    rng = rng or random.Random()
    current = plan
    cal = enrich_calendar(conn, profile, settings)
    t: ReplanTrigger = trigger
    for _ in range(max_calendar_passes):
        current = replan_affected_days(conn, profile, settings, current, t, rng=rng)
        if settings.google_calendar_enabled:
            current.meta.reason_codes = [
                r for r in current.meta.reason_codes if not r.startswith("calendar_no_slot:")
            ]
            current, reasons = assign_meals_to_calendar_slots(
                current,
                cal,
                profile.timezone,
                profile.planning_defaults.prep_buffer_minutes,
            )
            current.meta.reason_codes.extend(reasons)
        bad = set(slot_ids_calendar_unassigned(current))
        if not bad or not settings.google_calendar_enabled:
            break
        dates = dates_for_slot_ids(current, bad)
        t = ReplanTrigger(trigger="calendar_change", affected_dates=dates)
    return current
