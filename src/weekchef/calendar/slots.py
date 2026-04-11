"""Extract cook-sized slots from free/busy windows."""

from __future__ import annotations

from datetime import UTC, datetime

from weekchef.schemas import CalendarFreeBusy, TimeWindow, UserProfile


def _parse_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def refine_slots_for_cooking(
    raw: CalendarFreeBusy,
    profile: UserProfile,
    *,
    min_slot_minutes: int,
    max_slots_per_day: int,  # noqa: ARG001 — reserved for finer per-day capping later
) -> CalendarFreeBusy:
    """Keep only free intervals at least `min_slot_minutes` long (PoC: no per-day cap here)."""
    _ = profile
    _ = max_slots_per_day
    out: list[TimeWindow] = []
    for w in raw.free:
        a = _parse_iso(w.start)
        b = _parse_iso(w.end)
        if b <= a:
            continue
        if (b - a).total_seconds() / 60.0 < min_slot_minutes:
            continue
        out.append(TimeWindow(start=a.isoformat(), end=b.isoformat()))
    return CalendarFreeBusy(free=out)
