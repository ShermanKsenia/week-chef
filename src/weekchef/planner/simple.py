"""Naive weekly meal selection from retriever."""

from __future__ import annotations

import random
from datetime import date, timedelta

from psycopg import Connection

from weekchef.config import Settings
from weekchef.profile_utils import _banned_list, _cook_window_for_meal, _slot_budget_minutes
from weekchef.schemas import (
    CalendarFreeBusy,
    PlannedMeal,
    PlanDay,
    PlanMeta,
    RecipeFilters,
    SourceRef,
    UserProfile,
    WeeklyPlan,
)
from weekchef.tools.recipes import get_recipes


def plan_meal_slot(
    profile: UserProfile,
    conn: Connection,
    settings: Settings,
    day: date,
    meal_type: str,
    *,
    rng: random.Random,
    last_id: int | None = None,
) -> tuple[PlannedMeal | None, str | None]:
    """
    Pick one recipe for a single meal slot. Returns ``(meal, reason_code)``;
    ``reason_code`` is set when no recipe was found.
    """
    budget = _slot_budget_minutes(profile)
    banned = _banned_list(profile)
    filters = RecipeFilters(
        max_ready_minutes=budget,
        meal_types=[meal_type],
        banned_ingredient_substrings=banned,
    )
    res = get_recipes(conn, settings, filters, limit=80)
    if res.error:
        msg = (res.error or "").replace("\n", " ")[:200]
        return None, f"retriever_error:{res.code or 'unknown'}:{day.isoformat()}:{meal_type}:{msg}"
    if not res.items:
        return None, f"no_recipes:{day.isoformat()}:{meal_type}"
    candidates = [r for r in res.items if r.id != last_id]
    if not candidates:
        candidates = res.items
    choice = rng.choice(candidates)
    rm = choice.time_cook or budget
    slot_id = f"{day.isoformat()}_{meal_type.replace(' ', '_').lower()}"
    meal = PlannedMeal(
        slot_id=slot_id,
        meal_type=meal_type,
        recipe_id=str(choice.id),
        title=choice.name,
        ready_minutes=int(rm),
        cook_window=_cook_window_for_meal(profile, day, int(rm), meal_type),
        source_ref=SourceRef(link=choice.link),
    )
    return meal, None


def plan_simple_week(
    profile: UserProfile,
    conn: Connection,
    settings: Settings,
    *,
    calendar: CalendarFreeBusy | None = None,
    rng: random.Random | None = None,
) -> WeeklyPlan:
    # TODO: Phase 2 — Use calendar free slots to validate meal timing feasibility.
    # Calendar is passed but not used; future: filter recipes by available time windows.
    _ = calendar
    rng = rng or random.Random()
    meal_labels = profile.meal_types[: profile.meals_per_day]
    anchor = profile.week_anchor_date
    reason_codes: list[str] = []

    days_out: list[PlanDay] = []
    last_id: int | None = None

    for i in range(7):
        d = anchor + timedelta(days=i)
        meals: list[PlannedMeal] = []
        for meal_type in meal_labels:
            meal, err = plan_meal_slot(
                profile, conn, settings, d, meal_type, rng=rng, last_id=last_id
            )
            if err:
                reason_codes.append(err)
                continue
            assert meal is not None
            last_id = int(meal.recipe_id)
            meals.append(meal)
        days_out.append(PlanDay(date=d.isoformat(), meals=meals))

    return WeeklyPlan(
        week_start=anchor.isoformat(),
        days=days_out,
        meta=PlanMeta(
            pipeline_version=settings.pipeline_version,
            reason_codes=reason_codes,
        ),
    )
