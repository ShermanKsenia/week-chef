#!/usr/bin/env python3
"""
Read recipes CSV, normalize time_cook (minutes), ingredient and energy columns,
and write Parquet via pandas.

- time_cook: nullable integer minutes (pandas Int64); null if not a recognizable duration.
- ingredient: dict {ingredient_name: quantity_string}.
- energy: dict {calories|proteins|fats|carbohydrates: int}.

Requires: pandas, pyarrow (for to_parquet).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

# Whole-cell time patterns only (avoids picking minutes out of recipe text in bad rows).
_TIME_COOK_OK = re.compile(
    r"^(?P<m>\d+)\s+minutes?$|"
    r"^(?P<h>\d+)\s+hours?$|"
    r"^(?P<h2>\d+)\s+hours?\s+(?P<m2>\d+)\s+minutes?$|"
    r"^(?P<d>\d+)\s+days?$",
    re.IGNORECASE,
)


def parse_time_cook_minutes(raw: str) -> int | None:
    s = (raw or "").strip()
    if not s:
        return None
    m = _TIME_COOK_OK.match(s)
    if not m:
        return None
    if m.group("m") is not None:
        return int(m.group("m"))
    if m.group("h") is not None:
        return int(m.group("h")) * 60
    if m.group("h2") is not None:
        return int(m.group("h2")) * 60 + int(m.group("m2"))
    if m.group("d") is not None:
        return int(m.group("d")) * 24 * 60
    return None


_ING_SPLIT = re.compile(r", (?=[^:]+:)")


def parse_ingredient_dict(raw: str) -> dict[str, str]:
    s = (raw or "").strip()
    if not s:
        return {}
    out: dict[str, str] = {}
    for part in _ING_SPLIT.split(s):
        part = part.strip()
        if ":" not in part:
            continue
        name, qty = part.split(":", 1)
        name, qty = name.strip(), qty.strip()
        if name:
            out[name] = qty
    return out


_ENERGY_CAL = re.compile(r"(\d+)\s*kcal", re.IGNORECASE)
_ENERGY_MACRO = re.compile(
    r"(proteins|fats|carbohydrates)\s+(\d+)\s*grams?",
    re.IGNORECASE,
)


def parse_energy_dict(raw: str) -> dict[str, int]:
    s = (raw or "").strip()
    if not s:
        return {}
    out: dict[str, int] = {}
    m = _ENERGY_CAL.search(s)
    if m:
        out["calories"] = int(m.group(1))
    for m in _ENERGY_MACRO.finditer(s):
        key = m.group(1).lower()
        out[key] = int(m.group(2))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=Path("data/recipies_data.csv"),
        help="Input CSV path",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("data/recipies_data_transformed.parquet"),
        help="Output Parquet path",
    )
    parser.add_argument(
        "--compression",
        default="snappy",
        help="Parquet compression codec (snappy, zstd, gzip, none, …)",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.input, encoding="utf-8-sig")

    df["time_cook"] = (
        df["time_cook"].astype("string").map(parse_time_cook_minutes).astype("Int64")
    )
    df["ingredient"] = df["ingredient"].astype("string").map(parse_ingredient_dict)
    df["energy"] = df["energy"].astype("string").map(parse_energy_dict)

    df.to_parquet(
        args.output,
        engine="pyarrow",
        compression=None if args.compression == "none" else args.compression,
        index=False,
    )

    n_rows = len(df)
    n_empty_time = int(df["time_cook"].isna().sum())
    print(f"Wrote {n_rows} rows to {args.output}")
    print(f"Rows with null time_cook (unparsed): {n_empty_time}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
