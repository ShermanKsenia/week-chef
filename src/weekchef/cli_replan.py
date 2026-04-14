"""CLI: localized replan from an existing plan JSON."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from weekchef.config import get_settings
from weekchef.db.pool import sync_connection
from weekchef.orchestrator import replan_week
from weekchef.profile import load_profile
from weekchef.schemas import ReplanTrigger, WeeklyPlan
from weekchef.tools.validate_plan import validate_plan


def main_sync(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Re-plan affected days/slots from plan JSON.")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--plan-in", type=Path, dest="plan_in", required=True)
    parser.add_argument("--out", type=Path, default=Path("plan_replan.json"))
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--trigger",
        choices=["missed_meal", "calendar_change", "ingredient_unavailable"],
        default="calendar_change",
    )
    parser.add_argument(
        "--dates",
        type=str,
        default="",
        help="Comma-separated YYYY-MM-DD (optional; default depends on trigger)",
    )
    parser.add_argument(
        "--slot-ids",
        type=str,
        dest="slot_ids",
        default="",
        help="Comma-separated slot_id values (for missed_meal)",
    )
    parser.add_argument("--dsn", type=str, default=None)
    parser.add_argument("--max-calendar-passes", type=int, default=3)
    args = parser.parse_args(argv)

    profile_path = args.profile.expanduser().resolve()
    if not profile_path.is_file():
        print(
            "Error: profile file not found or not a regular file:\n"
            f"  {args.profile}\n"
            "Example: --profile fixtures/profile.json",
            file=sys.stderr,
        )
        return 2
    plan_in_path = args.plan_in.expanduser().resolve()
    if not plan_in_path.is_file():
        print(
            "Error: plan file not found or not a regular file:\n"
            f"  {args.plan_in}",
            file=sys.stderr,
        )
        return 2

    dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    slot_ids = [s.strip() for s in args.slot_ids.split(",") if s.strip()]

    trigger = ReplanTrigger(
        trigger=args.trigger,
        affected_dates=dates,
        meal_slot_ids=slot_ids or None,
    )

    settings = get_settings()
    dsn = args.dsn or settings.database_url
    profile = load_profile(profile_path)
    rng = random.Random(args.seed) if args.seed is not None else random.Random()

    raw = json.loads(plan_in_path.read_text(encoding="utf-8"))
    plan = WeeklyPlan.model_validate(raw)

    result = None
    try:
        with sync_connection(dsn) as conn:
            new_plan = replan_week(
                conn,
                profile,
                settings,
                plan,
                trigger,
                rng=rng,
                max_calendar_passes=args.max_calendar_passes,
            )
            result = validate_plan(new_plan, profile, conn, settings)
            new_plan.meta.reason_codes.extend(result.reason_codes)
            if not result.valid:
                new_plan.meta.reason_codes.insert(0, "validation_failed")
            plan = new_plan
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if result is None:
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(json.loads(plan.model_dump_json()), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote {args.out} (valid={result.valid})")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main_sync())
