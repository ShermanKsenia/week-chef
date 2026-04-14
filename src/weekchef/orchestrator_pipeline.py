"""Orchestrator pipeline: INTAKE → ENRICH → PLAN → VALIDATE → SHOPPING (LLM or deterministic)."""

from __future__ import annotations

import random
import time
from datetime import date, timedelta
from typing import Any

from psycopg import Connection
from pydantic import BaseModel, Field

from weekchef.config import Settings
from weekchef.llm.errors import LLMUnavailableError
from weekchef.llm.meal_plan import pick_recipe_for_slot_sync
from weekchef.llm.outputs import ParseInputResult
from weekchef.llm.parse_input import run_parse_input_sync
from weekchef.orchestrator import build_shopping_for_plan, enrich_calendar
from weekchef.planner.calendar_assign import assign_meals_to_calendar_slots
from weekchef.planner.simple import plan_simple_week
from weekchef.profile_utils import _banned_list, _cook_window_for_meal, _slot_budget_minutes
from weekchef.schemas import (
    PlannedMeal,
    PlanDay,
    PlanMeta,
    RecipeFilters,
    ShoppingListResult,
    SourceRef,
    UserProfile,
    ValidatePlanResult,
    WeeklyPlan,
)
from weekchef.observability.metrics import inc_validate_fail, record_plan_finished, record_validate_duration_ms
from weekchef.observability.spans import phase_span
from weekchef.tools.recipes import get_recipes
from weekchef.tools.validate_plan import validate_plan


def apply_parse_overrides(profile: UserProfile, parsed: Any) -> UserProfile:
    """Merge ``ParseInputResult``-like fields into a profile (returns new instance)."""
    data = profile.model_dump()
    if getattr(parsed, "servings", None) is not None:
        data["servings"] = int(parsed.servings)
    if getattr(parsed, "meals_per_day", None) is not None:
        data["meals_per_day"] = int(parsed.meals_per_day)
    extra_bans = list(getattr(parsed, "allergies_or_bans", None) or [])
    if extra_bans:
        r = dict(data.get("restrictions") or {})
        cur = set(r.get("banned_ingredient_substrings") or [])
        cur.update(extra_bans)
        r["banned_ingredient_substrings"] = sorted(cur)
        data["restrictions"] = r
    wk = getattr(parsed, "week_start_iso", None)
    if isinstance(wk, str) and wk.strip():
        try:
            data["week_anchor_date"] = date.fromisoformat(wk.strip()[:10])
        except ValueError:
            pass
    return UserProfile.model_validate(data)


class WeeklyPlanPipelineResult(BaseModel):
    phases_completed: list[str] = Field(default_factory=list)
    parse_result: ParseInputResult | None = None
    plan: WeeklyPlan
    validate_result: ValidatePlanResult
    shopping: ShoppingListResult | None = None
    fallback_used: bool = False
    llm_unavailable: bool = False


def _plan_week_llm(
    conn: Connection,
    profile: UserProfile,
    settings: Settings,
    *,
    rng: random.Random,
    client: Any | None = None,
) -> WeeklyPlan:
    meal_labels = profile.meal_types[: profile.meals_per_day]
    anchor = profile.week_anchor_date
    reason_codes: list[str] = []
    days_out: list[PlanDay] = []
    last_id: int | None = None
    budget = _slot_budget_minutes(profile)
    banned = _banned_list(profile)

    for i in range(7):
        d = anchor + timedelta(days=i)
        meals: list[PlannedMeal] = []
        for meal_type in meal_labels:
            filters = RecipeFilters(
                max_ready_minutes=budget,
                meal_types=[meal_type],
                banned_ingredient_substrings=banned,
            )
            res = get_recipes(conn, settings, filters, limit=80)
            if res.error:
                msg = (res.error or "").replace("\n", " ")[:200]
                reason_codes.append(
                    f"retriever_error:{res.code or 'unknown'}:{d.isoformat()}:{meal_type}:{msg}"
                )
                continue
            if not res.items:
                reason_codes.append(f"no_recipes:{d.isoformat()}:{meal_type}")
                continue
            candidates = [r for r in res.items if r.id != last_id] or list(res.items)
            try:
                picked = pick_recipe_for_slot_sync(
                    day_iso=d.isoformat(),
                    meal_type=meal_type,
                    candidates=candidates,
                    settings=settings,
                    client=client,
                )
            except (LLMUnavailableError, ValueError) as e:
                reason_codes.append(f"llm_pick_failed:{d.isoformat()}:{meal_type}:{e!s}")
                continue
            card = next((c for c in candidates if c.id == picked.recipe_id), None)
            if card is None:
                reason_codes.append(f"llm_bad_pick:{d.isoformat()}:{meal_type}")
                continue
            rm = card.time_cook or budget
            slot_id = f"{d.isoformat()}_{meal_type.replace(' ', '_').lower()}"
            meal = PlannedMeal(
                slot_id=slot_id,
                meal_type=meal_type,
                recipe_id=str(card.id),
                title=card.name,
                ready_minutes=int(rm),
                cook_window=_cook_window_for_meal(profile, d, int(rm), meal_type),
                source_ref=SourceRef(link=card.link),
            )
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


def run_weekly_plan_pipeline(
    conn: Connection,
    profile: UserProfile,
    settings: Settings,
    *,
    intake_user_message: str | None = None,
    rng: random.Random | None = None,
    client: Any | None = None,
) -> WeeklyPlanPipelineResult:
    """
    Run INTAKE (optional) → ENRICH → PLAN → VALIDATE → (shopping left to caller via flag).

    When ``settings.planner_use_llm`` is True, uses LLM for recipe selection per slot.
    On ``LLMUnavailableError`` or empty plan with ``planner_fallback_deterministic``,
    falls back to ``plan_simple_week``.
    """
    rng = rng or random.Random()
    phases: list[str] = []
    parsed = None
    working = profile

    if intake_user_message and intake_user_message.strip():
        with phase_span("INTAKE"):
            try:
                parsed = run_parse_input_sync(intake_user_message.strip(), settings=settings, client=client)
                working = apply_parse_overrides(working, parsed)
                phases.append("INTAKE")
            except LLMUnavailableError:
                if not settings.planner_fallback_deterministic:
                    return WeeklyPlanPipelineResult(
                        phases_completed=["INTAKE"],
                        parse_result=None,
                        plan=WeeklyPlan(week_start=working.week_anchor_date.isoformat(), days=[]),
                        validate_result=ValidatePlanResult(valid=False, reason_codes=["LLM_UNAVAILABLE"]),
                        fallback_used=False,
                        llm_unavailable=True,
                    )
                phases.append("INTAKE_SKIPPED_LLM_UNAVAILABLE")

    with phase_span("ENRICH"):
        cal = enrich_calendar(conn, working, settings)
        phases.append("ENRICH")

    use_llm = settings.planner_use_llm
    fallback = settings.planner_fallback_deterministic
    fb_used = False

    if use_llm:
        with phase_span("PLAN_LLM"):
            plan = _plan_week_llm(conn, working, settings, rng=rng, client=client)
            phases.append("PLAN_LLM")
            total_meals = sum(len(d.meals) for d in plan.days)
            if fallback and total_meals == 0:
                plan = plan_simple_week(working, conn, settings, calendar=cal, rng=rng)
                fb_used = True
                phases.append("PLAN_DETERMINISTIC_FALLBACK")
    else:
        with phase_span("PLAN_DETERMINISTIC"):
            plan = plan_simple_week(working, conn, settings, calendar=cal, rng=rng)
            phases.append("PLAN_DETERMINISTIC")

    with phase_span("AGGREGATE"):
        if settings.google_calendar_enabled:
            plan, cal_reasons = assign_meals_to_calendar_slots(
                plan,
                cal,
                working.timezone,
                working.planning_defaults.prep_buffer_minutes,
            )
            plan.meta.reason_codes.extend(cal_reasons)
        phases.append("AGGREGATE")

    with phase_span("VALIDATE"):
        t_val = time.perf_counter()
        val = validate_plan(plan, working, conn, settings)
        record_validate_duration_ms((time.perf_counter() - t_val) * 1000.0)
        phases.append("VALIDATE")

    if not val.valid:
        plan.meta.reason_codes = list(dict.fromkeys(plan.meta.reason_codes + val.reason_codes))
        plan.meta.reason_codes.insert(0, "validation_failed")

    return WeeklyPlanPipelineResult(
        phases_completed=phases,
        parse_result=parsed,
        plan=plan,
        validate_result=val,
        shopping=None,
        fallback_used=fb_used,
        llm_unavailable=False,
    )


def run_weekly_plan_pipeline_with_shopping(
    conn: Connection,
    profile: UserProfile,
    settings: Settings,
    *,
    intake_user_message: str | None = None,
    rng: random.Random | None = None,
    client: Any | None = None,
    subtract_inventory: bool = True,
) -> WeeklyPlanPipelineResult:
    """Same as ``run_weekly_plan_pipeline`` plus SHOPPING when validation passes."""
    t0 = time.perf_counter()
    out: WeeklyPlanPipelineResult | None = None
    try:
        base = run_weekly_plan_pipeline(
            conn,
            profile,
            settings,
            intake_user_message=intake_user_message,
            rng=rng,
            client=client,
        )
        shop: ShoppingListResult | None = None
        phases = list(base.phases_completed)
        if base.validate_result.valid:
            with phase_span("SHOPPING"):
                shop = build_shopping_for_plan(
                    conn,
                    profile,
                    settings,
                    base.plan,
                    subtract_inventory=subtract_inventory,
                )
                phases.append("SHOPPING")
        out = base.model_copy(update={"shopping": shop, "phases_completed": phases})
        return out
    finally:
        if out is not None:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            record_plan_finished(
                duration_ms=elapsed_ms,
                valid=out.validate_result.valid,
                fallback_used=out.fallback_used,
            )
            if not out.validate_result.valid:
                inc_validate_fail(list(out.validate_result.reason_codes))
