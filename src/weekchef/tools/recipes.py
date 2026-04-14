"""Tool: get_recipes (retriever)."""

from __future__ import annotations

from psycopg import Connection

from weekchef.db.recipes_repo import RecipesRepository
from weekchef.schemas import GetRecipesResult, RecipeCard, RecipeFilters


def get_recipes(
    conn: Connection,
    table_name: str,
    filters: RecipeFilters,
    limit: int,
) -> GetRecipesResult:
    try:
        repo = RecipesRepository(conn, table_name)
        items = repo.fetch(filters, limit)
        return GetRecipesResult(items=items)
    except OSError as e:
        conn.rollback()
        return GetRecipesResult(error=str(e), code="DB_ERROR")
    except Exception as e:  # noqa: BLE001 — PoC surface
        # Failed statements abort the transaction; reset so later queries work.
        conn.rollback()
        return GetRecipesResult(error=str(e), code="UPSTREAM_5xx")


def recipe_cards_to_tool_items(cards: list[RecipeCard]) -> list[dict]:
    """Narrow payload for LLM / logs (no full recipe text)."""
    return [
        {
            "recipe_id": c.id,
            "title": c.name,
            "ready_minutes": c.time_cook,
            "ingredients": [i.ingredient for i in c.ingredients[:20]],
            "tags": [c.label, c.type_kitchen],
            "source_ref": c.link,
        }
        for c in cards
    ]
