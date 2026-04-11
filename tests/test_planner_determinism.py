"""Planner uses seeded RNG (no DB — monkeypatch get_recipes)."""

from datetime import date
from unittest.mock import patch

from weekchef.config import Settings
from weekchef.schemas import RecipeCard, UserProfile
from weekchef.tools.recipes import GetRecipesResult


def _fake_get_recipes(*_args, **_kwargs) -> GetRecipesResult:
    return GetRecipesResult(
        items=[
            RecipeCard(
                id=1,
                name="A",
                label="Breakfast",
                time_cook=20,
                link="http://a",
            ),
            RecipeCard(
                id=2,
                name="B",
                label="Breakfast",
                time_cook=25,
                link="http://b",
            ),
        ]
    )


@patch("weekchef.planner.simple.get_recipes", side_effect=_fake_get_recipes)
def test_plan_reproducible_with_seed(_mock) -> None:
    import random

    from weekchef.planner.simple import plan_simple_week

    profile = UserProfile(
        week_anchor_date=date(2026, 4, 13),
        meals_per_day=1,
        meal_types=["Breakfast"],
    )
    settings = Settings()
    rng = random.Random(42)
    conn = None  # type: ignore[assignment]
    p1 = plan_simple_week(profile, conn, settings, rng=rng)  # type: ignore[arg-type]
    rng2 = random.Random(42)
    p2 = plan_simple_week(profile, conn, settings, rng=rng2)  # type: ignore[arg-type]
    assert p1.model_dump() == p2.model_dump()
