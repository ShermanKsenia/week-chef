"""Normalize ingredient lines from recipe JSON."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedIngredient:
    name_normalized: str
    quantity_raw: str


_NON_ALNUM = re.compile(r"[^a-z0-9а-яё]+", re.IGNORECASE)


def normalize_product_name(name: str) -> str:
    s = (name or "").strip().lower()
    s = _NON_ALNUM.sub(" ", s)
    return " ".join(s.split())


def parse_ingredient_item(ingredient: str, quantity: str) -> ParsedIngredient:
    return ParsedIngredient(
        name_normalized=normalize_product_name(ingredient),
        quantity_raw=(quantity or "").strip(),
    )


_QTY_NUM = re.compile(r"^([\d.,]+)\s*(.*)$")


def split_numeric_quantity(qty_raw: str) -> tuple[float | None, str]:
    """Best-effort: leading number → (value, rest)."""
    q = (qty_raw or "").strip()
    if not q:
        return None, ""
    m = _QTY_NUM.match(q.replace(",", "."))
    if not m:
        return None, q
    try:
        return float(m.group(1)), m.group(2).strip()
    except ValueError:
        return None, q


def merge_quantities(a: str, b: str) -> str:
    if not a:
        return b
    if not b:
        return a
    na, ua = split_numeric_quantity(a)
    nb, ub = split_numeric_quantity(b)
    if na is not None and nb is not None and normalize_unit(ua) == normalize_unit(ub):
        return f"{na + nb} {ua}".strip()
    return f"{a}; {b}"


def normalize_unit(u: str) -> str:
    return u.strip().lower()
