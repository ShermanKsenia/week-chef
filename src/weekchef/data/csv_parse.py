"""Parse raw CSV columns (shared with ETL)."""

from __future__ import annotations

import re

_TIME_COOK_OK = re.compile(
    r"^(?P<m>\d+)\s+minutes?$|"
    r"^(?P<h>\d+)\s+hours?$|"
    r"^(?P<h2>\d+)\s+hours?\s+(?P<m2>\d+)\s+minutes?$|"
    r"^(?P<d>\d+)\s+days?$",
    re.IGNORECASE,
)

_ING_SPLIT = re.compile(r", (?=[^:]+:)")

_ENERGY_CAL = re.compile(r"(\d+)\s*kcal", re.IGNORECASE)
_ENERGY_MACRO = re.compile(
    r"(proteins|fats|carbohydrates)\s+(\d+)\s*grams?",
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


def parse_ingredient_dict(raw: str) -> list[dict[str, str]]:
    s = (raw or "").strip()
    if not s:
        return []
    out: list[dict[str, str]] = []
    for part in _ING_SPLIT.split(s):
        part = part.strip()
        if ":" not in part:
            continue
        name, qty = part.split(":", 1)
        name, qty = name.strip(), qty.strip()
        if name:
            out.append({"ingredient": name, "quantity": qty})
    return out


def parse_energy_dict(raw: str) -> list[dict[str, int | str]]:
    s = (raw or "").strip()
    if not s:
        return []
    out: list[dict[str, int | str]] = []
    m = _ENERGY_CAL.search(s)
    if m:
        out.append({"energy": "calories", "quantity": int(m.group(1))})

    for m in _ENERGY_MACRO.finditer(s):
        key = m.group(1).lower()
        out.append({"energy": key, "quantity": int(m.group(2))})
    return out
