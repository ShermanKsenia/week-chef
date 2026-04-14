"""Tool: calendar_free_busy — Google Calendar API, free intervals only."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from weekchef.schemas import CalendarFreeBusy, TimeWindow, UserProfile


def _parse_rfc3339(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _merge_busy(busy: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    if not busy:
        return []
    busy = sorted(busy, key=lambda x: x[0])
    merged: list[tuple[datetime, datetime]] = []
    cur_s, cur_e = busy[0]
    for s, e in busy[1:]:
        if s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            merged.append((cur_s, cur_e))
            cur_s, cur_e = s, e
    merged.append((cur_s, cur_e))
    return merged


def _busy_to_free(
    window_start: datetime,
    window_end: datetime,
    busy_raw: list[dict[str, str]],
) -> list[tuple[datetime, datetime]]:
    busy_tuples = [
        (_parse_rfc3339(b["start"]), _parse_rfc3339(b["end"]))
        for b in busy_raw
        if "start" in b and "end" in b
    ]
    merged = _merge_busy(busy_tuples)
    free: list[tuple[datetime, datetime]] = []
    cur = window_start
    for bs, be in merged:
        if be <= window_start or bs >= window_end:
            continue
        bs = max(bs, window_start)
        be = min(be, window_end)
        if cur < bs:
            free.append((cur, bs))
        cur = max(cur, be)
    if cur < window_end:
        free.append((cur, window_end))
    return free


def week_window_utc(profile: UserProfile) -> tuple[datetime, datetime]:
    tz = ZoneInfo(profile.timezone)
    start_local = datetime.combine(profile.week_anchor_date, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=7)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def calendar_free_busy(
    creds: Credentials,
    calendar_id: str,
    time_min_iso: str,
    time_max_iso: str,
) -> CalendarFreeBusy:
    """
    Query FreeBusy and return only **free** intervals (RFC3339, UTC).
    Does not log or return event titles — busy times only.
    """
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    body = {
        "timeMin": time_min_iso,
        "timeMax": time_max_iso,
        "items": [{"id": calendar_id}],
    }
    fb = service.freebusy().query(body=body).execute()
    cal = fb.get("calendars", {}).get(calendar_id, {})
    busy_raw = cal.get("busy", [])
    w0 = _parse_rfc3339(time_min_iso)
    w1 = _parse_rfc3339(time_max_iso)
    free = _busy_to_free(w0, w1, busy_raw)
    return CalendarFreeBusy(
        free=[
            TimeWindow(start=a.isoformat(), end=b.isoformat())
            for a, b in free
        ]
    )


def calendar_free_busy_for_profile(
    creds: Credentials,
    calendar_id: str,
    profile: UserProfile,
) -> CalendarFreeBusy:
    w0, w1 = week_window_utc(profile)
    return calendar_free_busy(
        creds,
        calendar_id,
        w0.strftime("%Y-%m-%dT%H:%M:%SZ"),
        w1.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def synthetic_calendar_week(profile: UserProfile) -> CalendarFreeBusy:
    """Stub when Google Calendar is off: wide daily windows in user TZ."""
    tz = ZoneInfo(profile.timezone)
    anchor = profile.week_anchor_date
    free: list[TimeWindow] = []
    for i in range(7):
        d: date = anchor + timedelta(days=i)
        day_start = datetime(d.year, d.month, d.day, 8, 0, tzinfo=tz)
        day_end = datetime(d.year, d.month, d.day, 22, 0, tzinfo=tz)
        free.append(TimeWindow(start=day_start.isoformat(), end=day_end.isoformat()))
    return CalendarFreeBusy(free=free)
