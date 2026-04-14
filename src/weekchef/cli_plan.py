"""CLI: build weekly plan JSON (Phase 1)."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from weekchef.config import get_settings
from weekchef.db.pool import sync_connection
from weekchef.orchestrator import build_shopping_for_plan, build_weekly_plan
from weekchef.profile import load_profile
from weekchef.tools.validate_plan import validate_plan


def main_sync(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a naive weekly plan from PostgreSQL recipes.")
    parser.add_argument("--profile", type=Path, required=True, help="Path to profile JSON")
    parser.add_argument("--out", type=Path, default=Path("plan.json"), help="Output JSON path")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for reproducible plans")
    parser.add_argument(
        "--dsn",
        type=str,
        default=None,
        help="Override DATABASE_URL",
    )
    parser.add_argument(
        "--shopping-out",
        type=Path,
        default=None,
        help="Optional path to write shopping list JSON",
    )
    parser.add_argument(
        "--no-inventory-subtract",
        action="store_true",
        help="When writing shopping list, do not subtract weekchef_inventory",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    dsn = args.dsn or settings.database_url

    profile = load_profile(args.profile)
    rng = random.Random(args.seed) if args.seed is not None else random.Random()

    result = None
    shopping = None
    try:
        with sync_connection(dsn) as conn:
            plan = build_weekly_plan(conn, profile, settings, rng=rng)
            result = validate_plan(plan, profile, conn, settings)
            plan.meta.reason_codes.extend(result.reason_codes)
            if not result.valid:
                plan.meta.reason_codes.insert(0, "validation_failed")
            if args.shopping_out is not None:
                shopping = build_shopping_for_plan(
                    conn,
                    profile,
                    settings,
                    plan,
                    subtract_inventory=not args.no_inventory_subtract,
                )
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
    if args.shopping_out is not None and shopping is not None:
        args.shopping_out.parent.mkdir(parents=True, exist_ok=True)
        args.shopping_out.write_text(
            json.dumps(json.loads(shopping.model_dump_json()), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Wrote {args.shopping_out}")
    print(f"Wrote {args.out} (valid={result.valid})")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main_sync())
