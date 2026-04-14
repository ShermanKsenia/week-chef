"""Shared profile utilities for planning and validation."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from weekchef.schemas import CookWindow, UserProfile


def _slot_budget_minutes(profile: UserProfile) -> int:
    d = profile.planning_defaults
    return max(5, d.default_slot_minutes_if_no_calendar - d.prep_buffer_minutes)


def _banned_list(profile: UserProfile) -> list[str]:
    base = list(profile.restrictions.banned_ingredient_substrings)
    base.extend(profile.preferences.disliked_ingredient_substrings)
    return base


def _cook_window_for_meal(
    profile: UserProfile,
    day: date,
    ready_minutes: int,
    meal_type: str,
) -> CookWindow:
    tz = ZoneInfo(profile.timezone)

    meal_lower = meal_type.lower()
    default_hour = 12

    if "breakfast" in meal_lower or "завтрак" in meal_lower:
        default_hour = 8
    elif "lunch" in meal_lower or "обед" in meal_lower:
        default_hour = 13
    elif "dinner" in meal_lower or "supper" in meal_lower or "ужин" in meal_lower:
        default_hour = 19
    elif "snack" in meal_lower or "перекус" in meal_lower:
        default_hour = 15

    anchor = datetime(day.year, day.month, day.day, default_hour, 0, tzinfo=tz)
    half = max(5, (ready_minutes or 30) // 2)
    start = anchor - timedelta(minutes=half)
    end = start + timedelta(minutes=max(ready_minutes or 30, 10))
    return CookWindow(start=start.isoformat(), end=end.isoformat())


def extract_calories(quantity_str: str) -> int | None:
    """Extract numeric calories from quantity string.

    Handles formats like:
    - "200" → 200
    - "200 kcal" → 200
    - "200-250" → 225 (average of range)
    - "~200" → 200
    - "" → None
    """
    if not quantity_str or not str(quantity_str).strip():
        return None

    s = str(quantity_str).strip()
    range_match = re.search(r"(\d+)\s*[-—–]\s*(\d+)", s)
    if range_match:
        low = int(range_match.group(1))
        high = int(range_match.group(2))
        return (low + high) // 2

    single_match = re.search(r"\d+", s)
    if single_match:
        return int(single_match.group())

    return None
