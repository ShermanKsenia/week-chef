"""Heuristic grocery categories (PoC)."""

from __future__ import annotations

_DAIRY = ("milk", "cheese", "yogurt", "butter", "cream", "sour cream", "cottage", "молок", "сыр", "творог", "сметан", "йогурт")
_MEAT = ("chicken", "beef", "pork", "lamb", "sausage", "bacon", "fish", "salmon", "turkey", "куриц", "говядин", "свинин", "рыб", "бекон")
_BAKERY = ("flour", "bread", "pasta", "rice", "oats", "мука", "хлеб", "макарон", "рис", "круп")
_VEG = ("onion", "garlic", "tomato", "potato", "carrot", "pepper", "lettuce", "herb", "лук", "чеснок", "помидор", "картоф", "морков", "салат", "зелен")


def infer_category(product_normalized: str) -> str | None:
    p = product_normalized.lower()
    for k in _DAIRY:
        if k in p:
            return "dairy"
    for k in _MEAT:
        if k in p:
            return "meat_fish"
    for k in _BAKERY:
        if k in p:
            return "pantry"
    for k in _VEG:
        if k in p:
            return "vegetables"
    return None
