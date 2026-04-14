"""Tool: validate_plan — structural + constraint checks."""

from __future__ import annotations

from psycopg import Connection

from weekchef.config import Settings
from weekchef.db.recipes_repo import RecipesRepository
from weekchef.profile_utils import extract_calories
from weekchef.schemas import UserProfile, ValidatePlanResult, WeeklyPlan


def validate_plan(
    plan: WeeklyPlan,
    profile: UserProfile,
    conn: Connection,
    settings: Settings,
) -> ValidatePlanResult:
    repo = RecipesRepository(conn, settings.recipes_table)
    reason_codes: list[str] = []
    banned = [b.lower() for b in profile.restrictions.banned_ingredient_substrings]
    banned.extend(p.lower() for p in profile.preferences.disliked_ingredient_substrings)

    all_ids: list[int] = []
    for day in plan.days:
        for m in day.meals:
            try:
                all_ids.append(int(m.recipe_id))
            except ValueError:
                reason_codes.append("invalid_recipe_id")

    if reason_codes:
        return ValidatePlanResult(valid=False, reason_codes=reason_codes)

    by_id = repo.get_by_ids(all_ids)
    for day in plan.days:
        for m in day.meals:
            rid = int(m.recipe_id)
            card = by_id.get(rid)
            if card is None:
                reason_codes.append(f"missing_recipe:{m.recipe_id}")
                continue
            blob = card.name.lower() + " " + " ".join(
                i.ingredient.lower() for i in card.ingredients
            )
            if any(b in blob for b in banned):
                reason_codes.append(f"banned_ingredient:{m.slot_id}")

    if any(c.startswith("missing_recipe") for c in reason_codes):
        return ValidatePlanResult(valid=False, reason_codes=reason_codes)

    if profile.restrictions.strict and any(
        c.startswith("banned_ingredient") for c in reason_codes
    ):
        return ValidatePlanResult(valid=False, reason_codes=reason_codes)

    if profile.goal_calories_per_day is not None:
        total_kcal = 0
        n = 0
        for day in plan.days:
            for m in day.meals:
                card = by_id.get(int(m.recipe_id))
                if not card:
                    continue
                for e in card.energy:
                    if e.energy_type.lower() == "calories":
                        kcal = extract_calories(e.quantity)
                        if kcal is not None:
                            total_kcal += kcal
                            n += 1
        if n > 0 and total_kcal / 7 > profile.goal_calories_per_day * 1.5:
            reason_codes.append("calories_goal_soft_exceeded")

    return ValidatePlanResult(valid=True, reason_codes=reason_codes)
