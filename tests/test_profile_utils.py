"""Tests for weekchef.profile_utils."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from weekchef.config import Settings
from weekchef.profile_utils import (
    _cook_window_for_meal,
    extract_calories,
)
from weekchef.schemas import (
    CookWindow,
    EnergyItem,
    PlanDay,
    PlannedMeal,
    PlanMeta,
    Preferences,
    RecipeCard,
    Restrictions,
    UserProfile,
    WeeklyPlan,
)
from weekchef.tools.validate_plan import validate_plan


def _profile() -> UserProfile:
    return UserProfile(
        week_anchor_date=date(2026, 4, 14),
        timezone="Europe/Moscow",
        restrictions=Restrictions(),
        preferences=Preferences(),
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("200", 200),
        ("200 kcal", 200),
        ("200-250", 225),
        ("200—250", 225),
        ("200–250", 225),
        ("~200", 200),
        ("", None),
        ("   ", None),
        ("unknown", None),
    ],
)
def test_extract_calories(raw: str, expected: int | None) -> None:
    assert extract_calories(raw) == expected


def test_cook_window_breakfast_anchors_morning() -> None:
    p = _profile()
    cw = _cook_window_for_meal(p, date(2026, 4, 14), 30, "Breakfast")
    start = datetime.fromisoformat(cw.start)
    assert start.hour == 7 and start.minute == 45  # 8:00 - 15m


def test_cook_window_lunch_anchors_midday() -> None:
    p = _profile()
    cw = _cook_window_for_meal(p, date(2026, 4, 14), 20, "Lunch")
    start = datetime.fromisoformat(cw.start)
    assert start.hour == 12 and start.minute == 50  # 13:00 - 10m


def test_cook_window_dinner_anchors_evening() -> None:
    p = _profile()
    cw = _cook_window_for_meal(p, date(2026, 4, 14), 40, "Dinner")
    start = datetime.fromisoformat(cw.start)
    assert start.hour == 18 and start.minute == 40  # 19:00 - 20m


def test_cook_window_snack() -> None:
    p = _profile()
    cw = _cook_window_for_meal(p, date(2026, 4, 14), 30, "Snack")
    start = datetime.fromisoformat(cw.start)
    assert start.hour == 14 and start.minute == 45


def test_cook_window_unknown_meal_defaults_to_noon() -> None:
    p = _profile()
    cw = _cook_window_for_meal(p, date(2026, 4, 14), 30, "BrunchSpecial")
    start = datetime.fromisoformat(cw.start)
    assert start.hour == 11 and start.minute == 45


def test_validate_plan_calorie_range_not_concatenated_digits() -> None:
    """Regression: '200-250' must not become 200250 (would false-trigger soft calorie check)."""
    plan = WeeklyPlan(
        week_start="2026-04-14",
        days=[
            PlanDay(
                date="2026-04-14",
                meals=[
                    PlannedMeal(
                        slot_id="2026-04-14_breakfast",
                        meal_type="Breakfast",
                        recipe_id="1",
                        title="T",
                        ready_minutes=20,
                        cook_window=CookWindow(start="", end=""),
                    )
                ],
            )
        ],
        meta=PlanMeta(),
    )
    profile = UserProfile(
        week_anchor_date=date(2026, 4, 14),
        goal_calories_per_day=2000,
        restrictions=Restrictions(),
        preferences=Preferences(),
    )
    card = RecipeCard(
        id=1,
        name="Safe",
        ingredients=[],
        energy=[EnergyItem(energy_type="calories", quantity="200-250")],
    )
    conn = MagicMock()
    settings = Settings()

    with patch("weekchef.tools.validate_plan.RecipesRepository") as Repo:
        inst = MagicMock()
        inst.get_by_ids.return_value = {1: card}
        Repo.return_value = inst
        result = validate_plan(plan, profile, conn, settings)

    assert result.valid is True
    assert "calories_goal_soft_exceeded" not in result.reason_codes
