"""Phase 2: calendar slots, assignment, synthetic ENRICH."""

from datetime import date

from weekchef.calendar.slots import refine_slots_for_cooking
from weekchef.config import Settings
from weekchef.orchestrator import enrich_calendar
from weekchef.planner.calendar_assign import assign_meals_to_calendar_slots
from weekchef.schemas import (
    CalendarFreeBusy,
    CookWindow,
    PlannedMeal,
    PlanDay,
    PlanMeta,
    TimeWindow,
    UserProfile,
    WeeklyPlan,
)
from weekchef.tools.calendar import _busy_to_free, synthetic_calendar_week


def test_busy_to_free_simple() -> None:
    from datetime import UTC, datetime

    w0 = datetime(2026, 4, 13, 0, 0, tzinfo=UTC)
    w1 = datetime(2026, 4, 14, 0, 0, tzinfo=UTC)
    busy = [{"start": "2026-04-13T10:00:00Z", "end": "2026-04-13T11:00:00Z"}]
    free = _busy_to_free(w0, w1, busy)
    assert len(free) >= 1


def test_synthetic_week_has_seven_windows() -> None:
    p = UserProfile(week_anchor_date=date(2026, 4, 13))
    cal = synthetic_calendar_week(p)
    assert len(cal.free) == 7


def test_refine_drops_short_intervals() -> None:
    p = UserProfile(week_anchor_date=date(2026, 4, 13))
    raw = CalendarFreeBusy(
        free=[
            TimeWindow(start="2026-04-13T10:00:00+00:00", end="2026-04-13T10:05:00+00:00"),
            TimeWindow(start="2026-04-13T12:00:00+00:00", end="2026-04-13T14:00:00+00:00"),
        ]
    )
    refined = refine_slots_for_cooking(
        raw,
        p,
        min_slot_minutes=30,
        max_slots_per_day=8,
    )
    assert len(refined.free) == 1


def test_assign_fits_meal_into_slot() -> None:
    plan = WeeklyPlan(
        week_start="2026-04-13",
        days=[
            PlanDay(
                date="2026-04-13",
                meals=[
                    PlannedMeal(
                        slot_id="2026-04-13_breakfast",
                        meal_type="Breakfast",
                        recipe_id="1",
                        title="T",
                        ready_minutes=30,
                        cook_window=CookWindow(start="", end=""),
                    )
                ],
            )
        ],
        meta=PlanMeta(),
    )
    slots = CalendarFreeBusy(
        free=[
            TimeWindow(
                start="2026-04-13T08:00:00+03:00",
                end="2026-04-13T12:00:00+03:00",
            )
        ]
    )
    out, codes = assign_meals_to_calendar_slots(
        plan,
        slots,
        "Europe/Moscow",
        buffer_minutes=10,
    )
    assert not codes
    assert out.days[0].meals[0].cook_window.start


def test_enrich_offline_no_db_call_needed() -> None:
    from unittest.mock import MagicMock

    p = UserProfile(week_anchor_date=date(2026, 4, 13))
    settings = Settings(google_calendar_enabled=False)
    conn = MagicMock()
    cal = enrich_calendar(conn, p, settings)
    assert len(cal.free) == 7
    conn.cursor.assert_not_called()
