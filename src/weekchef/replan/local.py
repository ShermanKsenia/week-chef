"""Re-run meal selection for affected days or slots (no LLM)."""

from __future__ import annotations

import random
from datetime import date

from psycopg import Connection

from weekchef.config import Settings
from weekchef.planner.simple import plan_meal_slot
from weekchef.schemas import PlanDay, PlannedMeal, ReplanTrigger, UserProfile, WeeklyPlan


def _dates_to_touch(trigger: ReplanTrigger, plan: WeeklyPlan) -> set[str]:
    if trigger.affected_dates:
        return set(trigger.affected_dates)
    if trigger.trigger in ("calendar_change", "ingredient_unavailable"):
        return {d.date for d in plan.days}
    if trigger.trigger == "missed_meal" and trigger.meal_slot_ids:
        out: set[str] = set()
        want = set(trigger.meal_slot_ids)
        for day in plan.days:
            for m in day.meals:
                if m.slot_id in want:
                    out.add(day.date)
        return out
    return set()


def replan_affected_days(
    conn: Connection,
    profile: UserProfile,
    settings: Settings,
    plan: WeeklyPlan,
    trigger: ReplanTrigger,
    *,
    rng: random.Random | None = None,
) -> WeeklyPlan:
    """
    Replace meals on affected dates (or specific slots for ``missed_meal``).

    Calendar assignment is done by the orchestrator after this returns.
    """
    rng = rng or random.Random()
    dates = _dates_to_touch(trigger, plan)
    if not dates:
        return plan

    slot_filter: set[str] | None = None
    if trigger.trigger == "missed_meal" and trigger.meal_slot_ids:
        slot_filter = set(trigger.meal_slot_ids)

    new_days: list[PlanDay] = []
    last_id: int | None = None
    extra_reasons: list[str] = []

    for day in plan.days:
        if day.date not in dates:
            for m in day.meals:
                try:
                    last_id = int(m.recipe_id)
                except ValueError:
                    pass
            new_days.append(day)
            continue

        d = date.fromisoformat(day.date)

        if slot_filter:
            new_meals: list[PlannedMeal] = []
            for meal in day.meals:
                if meal.slot_id not in slot_filter:
                    new_meals.append(meal)
                    try:
                        last_id = int(meal.recipe_id)
                    except ValueError:
                        pass
                    continue
                picked, err = plan_meal_slot(
                    profile,
                    conn,
                    settings,
                    d,
                    meal.meal_type,
                    rng=rng,
                    last_id=last_id,
                )
                if err or picked is None:
                    if err:
                        extra_reasons.append(err)
                    new_meals.append(meal)
                    continue
                last_id = int(picked.recipe_id)
                new_meals.append(picked)
            new_days.append(PlanDay(date=day.date, meals=new_meals))
            continue

        meal_labels = profile.meal_types[: profile.meals_per_day]
        meals_out: list[PlannedMeal] = []
        for meal_type in meal_labels:
            picked, err = plan_meal_slot(
                profile,
                conn,
                settings,
                d,
                meal_type,
                rng=rng,
                last_id=last_id,
            )
            if err or picked is None:
                if err:
                    extra_reasons.append(err)
                continue
            last_id = int(picked.recipe_id)
            meals_out.append(picked)
        new_days.append(PlanDay(date=day.date, meals=meals_out))

    meta = plan.meta.model_copy()
    meta.reason_codes = list(meta.reason_codes)
    meta.reason_codes.extend(extra_reasons)
    meta.reason_codes.append("replan_localized")

    return WeeklyPlan(week_start=plan.week_start, days=new_days, meta=meta)
