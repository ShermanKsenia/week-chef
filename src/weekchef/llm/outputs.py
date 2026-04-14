"""Pydantic schemas for structured LLM outputs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ParseInputResult(BaseModel):
    """Structured output for INTAKE / parse_input."""

    intent_summary: str = ""
    servings: int | None = None
    meals_per_day: int | None = None
    dietary_notes: list[str] = Field(default_factory=list)
    allergies_or_bans: list[str] = Field(default_factory=list)
    week_start_iso: str | None = None
    missing_required_fields: list[str] = Field(default_factory=list)


class GenerateQuestionsResult(BaseModel):
    """Structured output for generate_questions (optional LLM path)."""

    assistant_reply: str = ""


class MealPickResult(BaseModel):
    """Pick one recipe from a candidate list (PLAN_DAYS)."""

    recipe_id: int
    rationale: str = ""
