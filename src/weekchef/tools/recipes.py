"""Tool: get_recipes (retriever)."""

from __future__ import annotations

import time

from psycopg import Connection

from weekchef.config import Settings
from weekchef.db.recipes_repo import RecipesRepository
from weekchef.observability.metrics import inc_get_recipes_result, record_get_recipes_ms
from weekchef.observability.spans import phase_span
from weekchef.schemas import GetRecipesResult, RecipeCard, RecipeFilters
from weekchef.tools.retriever_cache import global_retriever_cache, retriever_cache_key


def get_recipes(
    conn: Connection,
    settings: Settings,
    filters: RecipeFilters,
    limit: int,
) -> GetRecipesResult:
    table_name = settings.recipes_table
    cache = global_retriever_cache()
    cache_key = retriever_cache_key(table_name, filters, limit)
    t0 = time.perf_counter()
    result: GetRecipesResult | None = None
    try:
        with phase_span("get_recipes", {"weekchef.tool": "get_recipes"}):
            if settings.retriever_cache_enabled:
                hit = cache.get(cache_key)
                if hit is not None:
                    result = hit
                    return result
            try:
                repo = RecipesRepository(conn, table_name)
                items = repo.fetch(filters, limit)
                result = GetRecipesResult(items=items)
                if settings.retriever_cache_enabled:
                    cache.set(cache_key, result, float(settings.retriever_cache_ttl_seconds))
                return result
            except OSError as e:
                conn.rollback()
                result = GetRecipesResult(error=str(e), code="DB_ERROR")
                return result
            except Exception as e:  # noqa: BLE001 — PoC surface
                conn.rollback()
                result = GetRecipesResult(error=str(e), code="UPSTREAM_5xx")
                return result
    finally:
        if result is not None:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            tool_result = "error" if result.error else "ok"
            code = (result.code or "") if result.error else "ok"
            record_get_recipes_ms(elapsed_ms, tool_result=tool_result, code=code)
            inc_get_recipes_result(tool_result=tool_result, code=code)


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
