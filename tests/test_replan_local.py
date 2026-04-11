"""Localized replan (mocked recipe picks)."""

from datetime import date
from unittest.mock import patch

from weekchef.config import Settings
from weekchef.schemas import (
    CookWindow,
    PlanDay,
    PlannedMeal,
    PlanMeta,
    ReplanTrigger,
    SourceRef,
    UserProfile,
    WeeklyPlan,
)
from weekchef.replan.local import replan_affected_days


def _meal(slot: str, rid: str) -> PlannedMeal:
    return PlannedMeal(
        slot_id=slot,
        meal_type="Breakfast",
        recipe_id=rid,
        title="T",
        ready_minutes=15,
        cook_window=CookWindow(start="2026-04-13T12:00:00", end="2026-04-13T12:20:00"),
        source_ref=SourceRef(),
    )


@patch("weekchef.replan.local.plan_meal_slot")
def test_replan_single_slot(mock_pick) -> None:
    mock_pick.return_value = (
        _meal("2026-04-13_breakfast", "99"),
        None,
    )
    plan = WeeklyPlan(
        week_start="2026-04-13",
        days=[PlanDay(date="2026-04-13", meals=[_meal("2026-04-13_breakfast", "1")])],
        meta=PlanMeta(),
    )
    profile = UserProfile(week_anchor_date=date(2026, 4, 13), meals_per_day=1, meal_types=["Breakfast"])
    trigger = ReplanTrigger(trigger="missed_meal", meal_slot_ids=["2026-04-13_breakfast"])
    conn = None  # type: ignore[arg-type]
    out = replan_affected_days(conn, profile, Settings(), plan, trigger)
    assert out.days[0].meals[0].recipe_id == "99"
    assert "replan_localized" in out.meta.reason_codes


@patch("weekchef.replan.local.plan_meal_slot")
def test_replan_full_day(mock_pick) -> None:
    calls = {"n": 0}

    def side_effect(*_a, **_k):
        calls["n"] += 1
        return _meal("2026-04-13_breakfast", str(10 + calls["n"])), None

    mock_pick.side_effect = side_effect
    plan = WeeklyPlan(
        week_start="2026-04-13",
        days=[PlanDay(date="2026-04-13", meals=[_meal("2026-04-13_breakfast", "1")])],
        meta=PlanMeta(),
    )
    profile = UserProfile(week_anchor_date=date(2026, 4, 13), meals_per_day=1, meal_types=["Breakfast"])
    trigger = ReplanTrigger(trigger="calendar_change", affected_dates=["2026-04-13"])
    conn = None  # type: ignore[arg-type]
    out = replan_affected_days(conn, profile, Settings(), plan, trigger)
    assert out.days[0].meals[0].recipe_id == "11"
