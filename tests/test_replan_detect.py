"""Replan conflict detection."""

from weekchef.replan.detect import dates_for_slot_ids, slot_ids_calendar_unassigned
from weekchef.schemas import CookWindow, PlanDay, PlannedMeal, PlanMeta, SourceRef, WeeklyPlan


def test_slot_ids_calendar_unassigned() -> None:
    plan = WeeklyPlan(
        week_start="2026-04-13",
        days=[],
        meta=PlanMeta(reason_codes=["calendar_no_slot:2026-04-13_breakfast", "other"]),
    )
    assert slot_ids_calendar_unassigned(plan) == ["2026-04-13_breakfast"]


def test_dates_for_slot_ids() -> None:
    m = PlannedMeal(
        slot_id="s1",
        meal_type="Lunch",
        recipe_id="1",
        title="",
        ready_minutes=10,
        cook_window=CookWindow(start="2026-04-14T12:00:00", end="2026-04-14T12:30:00"),
        source_ref=SourceRef(),
    )
    plan = WeeklyPlan(
        week_start="2026-04-13",
        days=[PlanDay(date="2026-04-14", meals=[m])],
        meta=PlanMeta(),
    )
    assert dates_for_slot_ids(plan, {"s1"}) == ["2026-04-14"]
