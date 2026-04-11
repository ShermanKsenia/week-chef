"""Read recipes from PostgreSQL `recipies_db` table."""

from __future__ import annotations

import json
from typing import Any

from psycopg import Connection
from psycopg import sql

from weekchef.schemas import IngredientItem, EnergyItem, RecipeCard, RecipeFilters


class RecipesRepository:
    def __init__(self, conn: Connection, table_name: str) -> None:
        self._conn = conn
        self._table = table_name

    def _parse_row(self, row: tuple[Any, ...]) -> RecipeCard:
        (
            rid,
            name,
            text,
            type_kitchen,
            link,
            label,
            time_cook,
            ingredients_raw,
            energy_raw,
        ) = row
        ing = ingredients_raw if isinstance(ingredients_raw, list) else json.loads(ingredients_raw or "[]")
        en = energy_raw if isinstance(energy_raw, list) else json.loads(energy_raw or "[]")
        return RecipeCard(
            id=int(rid),
            name=name or "",
            text=text or "",
            type_kitchen=type_kitchen or "",
            link=link or "",
            label=label or "",
            time_cook=int(time_cook) if time_cook is not None else None,
            ingredients=[IngredientItem.model_validate(x) for x in ing],
            energy=[EnergyItem.model_validate(x) for x in en],
        )

    def fetch(self, filters: RecipeFilters, limit: int) -> list[RecipeCard]:
        parts: list[sql.SQL | sql.Composed] = [
            sql.SQL(
                "SELECT id, name, text, type_kitchen, link, label, time_cook, ingredients, energy FROM "
            ),
            sql.Identifier(self._table),
            sql.SQL(" WHERE 1=1 "),
        ]
        params: list[Any] = []
        if filters.max_ready_minutes is not None:
            parts.append(sql.SQL(" AND time_cook IS NOT NULL AND time_cook <= %s "))
            params.append(filters.max_ready_minutes)
        if filters.meal_types:
            parts.append(sql.SQL(" AND label = ANY(%s) "))
            params.append(filters.meal_types)
        parts.append(sql.SQL(" ORDER BY id "))
        parts.append(sql.SQL(" LIMIT %s "))
        params.append(limit * 20)

        query = sql.Composed(parts)
        with self._conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        out: list[RecipeCard] = []
        banned = [b.lower() for b in filters.banned_ingredient_substrings]
        for row in rows:
            card = self._parse_row(row)
            ing_blob = " ".join(i.ingredient.lower() for i in card.ingredients)
            blob = f"{card.name.lower()} {ing_blob}"
            if any(b in blob for b in banned):
                continue
            out.append(card)
            if len(out) >= limit:
                break
        return out

    def get_by_ids(self, ids: list[int]) -> dict[int, RecipeCard]:
        if not ids:
            return {}
        q = sql.SQL(
            "SELECT id, name, text, type_kitchen, link, label, time_cook, ingredients, energy FROM {} WHERE id = ANY(%s)"
        ).format(sql.Identifier(self._table))
        with self._conn.cursor() as cur:
            cur.execute(q, (ids,))
            rows = cur.fetchall()
        return {int(r[0]): self._parse_row(r) for r in rows}
