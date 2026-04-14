"""LLM-assisted recipe choice for a single meal slot."""

from __future__ import annotations

import json
from typing import Any

from weekchef.config import Settings, get_settings
from weekchef.llm.completions import complete_json_sync
from weekchef.llm.outputs import MealPickResult
from weekchef.llm.prompts import MEAL_PICK_SYSTEM, MEAL_PICK_VERSION
from weekchef.schemas import RecipeCard


def pick_recipe_for_slot_sync(
    *,
    day_iso: str,
    meal_type: str,
    candidates: list[RecipeCard],
    settings: Settings | None = None,
    client: Any | None = None,
) -> MealPickResult:
    """Ask the model to pick ``recipe_id`` from ``candidates`` only."""
    s = settings or get_settings()
    narrow = [
        {"recipe_id": c.id, "title": c.name, "ready_minutes": c.time_cook}
        for c in candidates[:40]
    ]
    user = json.dumps(
        {
            "day": day_iso,
            "meal_type": meal_type,
            "candidates": narrow,
        },
        ensure_ascii=False,
    )
    messages: list[dict[str, str]] = [
        {"role": "system", "content": MEAL_PICK_SYSTEM},
        {"role": "user", "content": user},
    ]
    picked = complete_json_sync(
        messages,
        MealPickResult,
        settings=s,
        client=client,
        temperature=0.2,
        max_tokens=256,
        llm_step="meal_pick",
        prompt_version=MEAL_PICK_VERSION,
    )
    allowed = {c.id for c in candidates}
    if picked.recipe_id not in allowed:
        raise ValueError(f"recipe_id {picked.recipe_id} not in candidates")
    return picked
