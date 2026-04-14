"""Assign planned meals to concrete cook windows using calendar slots."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from weekchef.schemas import CalendarFreeBusy, CookWindow, PlannedMeal, PlanDay, WeeklyPlan


def _parse_aware(s: str, default_tz: ZoneInfo) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=default_tz)
    return dt


def _overlaps_local_day(ss: datetime, ee: datetime, d: date, tz: ZoneInfo) -> bool:
    sl = ss.astimezone(tz)
    el = ee.astimezone(tz)
    day0 = datetime(d.year, d.month, d.day, tzinfo=tz)
    day1 = day0 + timedelta(days=1)
    return sl < day1 and el > day0


def assign_meals_to_calendar_slots(
    plan: WeeklyPlan,
    slots: CalendarFreeBusy,
    timezone_name: str,
    buffer_minutes: int,
) -> tuple[WeeklyPlan, list[str]]:
    """
    Greedy: for each meal, pick the first unused slot overlapping that **local** calendar day
    where clipped segment fits ready_minutes + buffer.
    """
    tz = ZoneInfo(timezone_name)
    reason_codes: list[str] = []

    pool: list[tuple[datetime, datetime]] = []
    for w in slots.free:
        ss = _parse_aware(w.start, tz)
        ee = _parse_aware(w.end, tz)
        pool.append((ss, ee))

    used: set[int] = set()
    new_days: list[PlanDay] = []

    for day in plan.days:
        meal_date = date.fromisoformat(day.date)
        new_meals: list[PlannedMeal] = []
        for meal in day.meals:
            need = meal.ready_minutes + buffer_minutes
            placed = False
            day0 = datetime(meal_date.year, meal_date.month, meal_date.day, tzinfo=tz)
            day1 = day0 + timedelta(days=1)

            for idx, (ss, ee) in enumerate(pool):
                if idx in used:
                    continue
                if not _overlaps_local_day(ss, ee, meal_date, tz):
                    continue
                seg_start = max(ss.astimezone(tz), day0)
                seg_end = min(ee.astimezone(tz), day1)
                avail = int((seg_end - seg_start).total_seconds() // 60)
                if avail >= need:
                    used.add(idx)
                    cook_end = seg_start + timedelta(minutes=meal.ready_minutes)
                    new_meals.append(
                        meal.model_copy(
                            update={
                                "cook_window": CookWindow(
                                    start=seg_start.isoformat(),
                                    end=cook_end.isoformat(),
                                )
                            }
                        )
                    )
                    placed = True
                    break
            if not placed:
                reason_codes.append(f"calendar_no_slot:{meal.slot_id}")
                new_meals.append(meal)
        new_days.append(PlanDay(date=day.date, meals=new_meals))

    new_plan = WeeklyPlan(week_start=plan.week_start, days=new_days, meta=plan.meta)
    return new_plan, reason_codes
