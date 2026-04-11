"""Shopping list aggregation (mocked DB)."""

from unittest.mock import MagicMock, patch

from weekchef.config import Settings
from weekchef.schemas import IngredientItem, RecipeCard, WeeklyPlan
from weekchef.tools.shopping import build_shopping_list, recipe_ids_from_plan


def _card(rid: int, name: str, ings: list[tuple[str, str]]) -> RecipeCard:
    return RecipeCard(
        id=rid,
        name=name,
        ingredients=[IngredientItem(ingredient=a, quantity=b) for a, b in ings],
    )


@patch("weekchef.tools.shopping.RecipesRepository")
def test_build_shopping_list_merges_same_ingredient(mock_repo_cls: MagicMock) -> None:
    conn = MagicMock()
    repo = MagicMock()
    mock_repo_cls.return_value = repo
    repo.get_by_ids.return_value = {
        1: _card(1, "A", [("Milk", "200 ml"), ("Sugar", "10 g")]),
        2: _card(2, "B", [("milk", "100 ml")]),
    }

    res = build_shopping_list(conn, Settings(), [1, 2], servings=2, subtract_inventory=False)
    assert res.error is None
    by_name = {line.product.lower(): line for line in res.lines}
    assert "milk" in by_name
    assert by_name["milk"].qty == 600.0
    assert by_name["milk"].unit == "ml"


@patch("weekchef.tools.shopping.inventory_list")
@patch("weekchef.tools.shopping.RecipesRepository")
def test_subtract_inventory_full_cover(
    mock_repo_cls: MagicMock, mock_inv: MagicMock
) -> None:
    conn = MagicMock()
    repo = MagicMock()
    mock_repo_cls.return_value = repo
    repo.get_by_ids.return_value = {
        1: _card(1, "A", [("Salt", "5 g")]),
    }
    mock_inv.return_value = [{"name_normalized": "salt", "qty": 10.0, "unit": "g"}]

    res = build_shopping_list(
        conn,
        Settings(),
        [1],
        servings=1,
        subtract_inventory=True,
        user_key="u1",
    )
    assert res.error is None
    salt = next(x for x in res.lines if "salt" in x.product.lower())
    assert salt.already_have is True
    assert salt.qty == 0.0


def test_recipe_ids_from_plan_order() -> None:
    from weekchef.schemas import CookWindow, PlanDay, PlannedMeal, PlanMeta, SourceRef

    plan = WeeklyPlan(
        week_start="2026-04-13",
        days=[
            PlanDay(
                date="2026-04-13",
                meals=[
                    PlannedMeal(
                        slot_id="a",
                        meal_type="Lunch",
                        recipe_id="7",
                        title="T",
                        ready_minutes=10,
                        cook_window=CookWindow(start="2026-04-13T12:00:00", end="2026-04-13T12:30:00"),
                        source_ref=SourceRef(),
                    ),
                    PlannedMeal(
                        slot_id="b",
                        meal_type="Dinner",
                        recipe_id="7",
                        title="T2",
                        ready_minutes=10,
                        cook_window=CookWindow(start="2026-04-13T18:00:00", end="2026-04-13T18:30:00"),
                        source_ref=SourceRef(),
                    ),
                ],
            )
        ],
        meta=PlanMeta(),
    )
    assert recipe_ids_from_plan(plan) == [7]
