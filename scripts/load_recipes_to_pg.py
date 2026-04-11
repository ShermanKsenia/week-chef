#!/usr/bin/env python3
"""Bulk load CSV into PostgreSQL table recipies_db (JSON ingredients/energy arrays)."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

# Allow running without pip install when repo root is on PYTHONPATH
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

import psycopg
from psycopg import sql

from weekchef.data.csv_parse import (
    parse_energy_dict,
    parse_ingredient_dict,
    parse_time_cook_minutes,
)


def _energy_rows_for_db(parsed: list[dict]) -> list[dict[str, str]]:
    """Match RecipeCard / DB JSON: energy_type + string quantity."""
    out: list[dict[str, str]] = []
    for x in parsed:
        et = x["energy"]
        q = x["quantity"]
        if et == "calories":
            out.append({"energy_type": "calories", "quantity": f"{q} kcal"})
        else:
            out.append({"energy_type": et, "quantity": f"{q} grams"})
    return out


def load_rows(csv_path: Path) -> list[tuple]:
    rows: list[tuple] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            name = (r.get("name") or "").strip()
            if not name:
                continue
            tc = parse_time_cook_minutes(r.get("time_cook") or "")
            ing = parse_ingredient_dict(r.get("ingredient") or "")
            en = _energy_rows_for_db(parse_energy_dict(r.get("energy") or ""))
            rows.append(
                (
                    name,
                    (r.get("text") or "").strip(),
                    (r.get("type_kitchen") or "").strip(),
                    (r.get("link") or "").strip(),
                    (r.get("label") or "").strip(),
                    tc,
                    json.dumps(ing),
                    json.dumps(en),
                )
            )
    return rows


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("-i", "--input", type=Path, default=Path("data/recipies_data.csv"))
    p.add_argument(
        "--dsn",
        default=os.environ.get("DATABASE_URL", "postgresql://localhost:5432/mydb"),
    )
    p.add_argument("--table", default=os.environ.get("RECIPES_TABLE", "recipies_db"))
    p.add_argument("--truncate", action="store_true", help="TRUNCATE table before load")
    args = p.parse_args()

    if not args.input.is_file():
        print(f"Missing CSV: {args.input}", file=sys.stderr)
        return 1

    data = load_rows(args.input)
    insert = sql.SQL(
        "INSERT INTO {} (name, text, type_kitchen, link, label, time_cook, ingredients, energy) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)"
    ).format(sql.Identifier(args.table))

    with psycopg.connect(args.dsn) as conn:
        with conn.cursor() as cur:
            if args.truncate:
                cur.execute(
                    sql.SQL("TRUNCATE {} RESTART IDENTITY").format(sql.Identifier(args.table))
                )
            for row in data:
                cur.execute(insert, row)
        conn.commit()

    print(f"Inserted {len(data)} rows into {args.table}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
