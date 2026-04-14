"""Tool: build_shopping_list."""

from __future__ import annotations

from typing import TYPE_CHECKING

from psycopg import Connection

if TYPE_CHECKING:
    from weekchef.schemas import WeeklyPlan

from weekchef.config import Settings
from weekchef.db.inventory import inventory_list
from weekchef.db.recipes_repo import RecipesRepository
from weekchef.schemas import ShoppingLine, ShoppingListResult
from weekchef.shopping.categories import infer_category
from weekchef.shopping.parse_ingredients import (
    merge_quantities,
    parse_ingredient_item,
    split_numeric_quantity,
)


def _scale_qty_str(qty_raw: str, factor: float) -> str:
    if factor == 1.0 or not qty_raw:
        return qty_raw
    num, rest = split_numeric_quantity(qty_raw)
    if num is None:
        return qty_raw
    scaled = num * factor
    if scaled == int(scaled):
        return f"{int(scaled)} {rest}".strip()
    return f"{scaled:.2g} {rest}".strip()


def build_shopping_list(
    conn: Connection,
    settings: Settings,
    recipe_ids: list[int],
    servings: int,
    *,
    subtract_inventory: bool = False,
    user_key: str | None = None,
    default_recipe_servings: int = 1,
) -> ShoppingListResult:
    """
    Aggregate ingredients from recipes; scale by ``servings / default_recipe_servings``.
    Optionally subtract user's pantry (exact normalized name match + numeric qty when possible).
    """
    try:
        repo = RecipesRepository(conn, settings.recipes_table)
        by_id = repo.get_by_ids(recipe_ids)
    except Exception as e:  # noqa: BLE001
        conn.rollback()
        return ShoppingListResult(error=str(e), code="DB_ERROR")

    factor = servings / max(1, default_recipe_servings)
    merged: dict[str, str] = {}
    display_name: dict[str, str] = {}

    for rid in recipe_ids:
        card = by_id.get(rid)
        if not card:
            continue
        for ing in card.ingredients:
            p = parse_ingredient_item(ing.ingredient, ing.quantity)
            key = p.name_normalized
            if not key:
                continue
            scaled = _scale_qty_str(p.quantity_raw, factor)
            if key not in display_name:
                display_name[key] = ing.ingredient.strip()
            merged[key] = merge_quantities(merged.get(key, ""), scaled)

    lines: list[ShoppingLine] = []
    for key, qty_str in sorted(merged.items()):
        num, unit = split_numeric_quantity(qty_str)
        cat = infer_category(key)
        lines.append(
            ShoppingLine(
                product=display_name.get(key, key),
                qty=num,
                unit=unit,
                category=cat,
                already_have=False,
            )
        )

    if subtract_inventory and user_key:
        inv = {r["name_normalized"]: r for r in inventory_list(conn, user_key)}
        adjusted: list[ShoppingLine] = []
        for line in lines:
            key = parse_ingredient_item(line.product, "").name_normalized
            row = inv.get(key)
            if not row or row.get("qty") is None:
                adjusted.append(line)
                continue
            have = float(row["qty"])
            need = line.qty
            iunit = (row.get("unit") or "").lower()
            lunit = line.unit.lower()
            if need is not None and iunit == lunit and have >= need:
                adjusted.append(line.model_copy(update={"already_have": True, "qty": 0.0}))
            elif need is not None and iunit == lunit and have > 0:
                rest = max(0.0, need - have)
                adjusted.append(
                    line.model_copy(
                        update={
                            "qty": rest if rest > 0 else None,
                            "already_have": rest <= 0,
                        }
                    )
                )
            else:
                adjusted.append(line)
        lines = adjusted

    return ShoppingListResult(lines=lines)


def recipe_ids_from_plan(plan: WeeklyPlan) -> list[int]:
    """Collect unique recipe ids from a WeeklyPlan."""
    ids: list[int] = []
    seen: set[int] = set()
    for day in plan.days:
        for m in day.meals:
            try:
                rid = int(m.recipe_id)
            except ValueError:
                continue
            if rid not in seen:
                seen.add(rid)
                ids.append(rid)
    return ids
