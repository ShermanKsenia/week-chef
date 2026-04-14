"""Post-filter recipes by meal slot hints (label / kitchen / name), retriever contract."""

from __future__ import annotations

from weekchef.schemas import RecipeCard

# English + Russian keywords for planner meal_types (Breakfast, Lunch, …)
_MEAL_TERMS: dict[str, tuple[str, ...]] = {
    "breakfast": ("breakfast", "завтрак", "утро"),
    "lunch": ("lunch", "обед", "ланч"),
    "dinner": ("dinner", "ужин", "вечер", "супер"),
    "snack": ("snack", "перекус", "полдник"),
}


def _expand_hints(hints: list[str]) -> set[str]:
    terms: set[str] = set()
    for h in hints:
        s = (h or "").strip().lower()
        if not s:
            continue
        terms.add(s)
        for key, variants in _MEAL_TERMS.items():
            if s == key or s in key or key in s:
                terms.update(variants)
    return terms


def recipe_matches_meal_hints(card: RecipeCard, hints: list[str] | None) -> bool:
    """True if recipe metadata plausibly matches requested meal slots (soft matching)."""
    if not hints:
        return True
    blob = f"{card.label} {card.type_kitchen} {card.name}".lower()
    terms = _expand_hints(hints)
    return any(t in blob for t in terms)


def filter_by_meal_hints_or_fallback(cards: list[RecipeCard], hints: list[str] | None) -> list[RecipeCard]:
    """Prefer cards matching ``hints``; if none match, return ``cards`` unchanged (planner still gets candidates)."""
    if not hints:
        return cards
    matched = [c for c in cards if recipe_matches_meal_hints(c, hints)]
    return matched if matched else cards
