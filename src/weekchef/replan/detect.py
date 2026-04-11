"""Detect when a plan conflicts with calendar or needs follow-up."""

from __future__ import annotations

from weekchef.schemas import WeeklyPlan


def slot_ids_calendar_unassigned(plan: WeeklyPlan) -> list[str]:
    """Slot ids that still lack a fitting calendar window (see ``calendar_assign``)."""
    prefix = "calendar_no_slot:"
    out: list[str] = []
    for code in plan.meta.reason_codes:
        if code.startswith(prefix):
            out.append(code.removeprefix(prefix))
    return out


def dates_for_slot_ids(plan: WeeklyPlan, slot_ids: set[str]) -> list[str]:
    """Resolve local calendar dates for the given meal slot ids."""
    found: set[str] = set()
    for day in plan.days:
        for m in day.meals:
            if m.slot_id in slot_ids:
                found.add(day.date)
    return sorted(found)
