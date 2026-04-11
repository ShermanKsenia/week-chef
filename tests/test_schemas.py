"""Round-trip Pydantic models."""

import json
from datetime import date

from weekchef.schemas import UserProfile, WeeklyPlan


def test_profile_roundtrip() -> None:
    p = UserProfile(
        week_anchor_date=date(2026, 4, 13),
        user_id="u1",
    )
    raw = p.model_dump_json()
    p2 = UserProfile.model_validate_json(raw)
    assert p2.user_id == "u1"
    assert p2.week_anchor_date == date(2026, 4, 13)


def test_weekly_plan_json_keys() -> None:
    w = WeeklyPlan.model_validate_json(
        json.dumps(
            {
                "week_start": "2026-04-13",
                "days": [],
                "meta": {"pipeline_version": "0.1.0", "reason_codes": []},
            }
        )
    )
    assert w.week_start == "2026-04-13"
