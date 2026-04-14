"""Meal hint post-filter for retriever."""

from weekchef.db.recipe_meal_filter import filter_by_meal_hints_or_fallback, recipe_matches_meal_hints
from weekchef.schemas import RecipeCard


def test_meal_hint_matches_label() -> None:
    c = RecipeCard(id=1, name="Porridge", label="завтрак", time_cook=15)
    assert recipe_matches_meal_hints(c, ["Breakfast"]) is True


def test_meal_filter_fallback_when_no_match() -> None:
    c = RecipeCard(id=1, name="X", label="unknown", time_cook=15)
    out = filter_by_meal_hints_or_fallback([c], ["Breakfast"])
    assert len(out) == 1 and out[0].id == 1
