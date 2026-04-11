"""Pydantic models for profiles, recipes, plans, and tools."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class IngredientItem(BaseModel):
    ingredient: str
    quantity: str


class EnergyItem(BaseModel):
    energy_type: str
    quantity: str


class RecipeCard(BaseModel):
    id: int
    name: str
    text: str = ""
    type_kitchen: str = ""
    link: str = ""
    label: str = ""
    time_cook: int | None = None
    ingredients: list[IngredientItem] = Field(default_factory=list)
    energy: list[EnergyItem] = Field(default_factory=list)


class RecipeFilters(BaseModel):
    max_ready_minutes: int | None = None
    meal_types: list[str] | None = None
    banned_ingredient_substrings: list[str] = Field(default_factory=list)


class Restrictions(BaseModel):
    banned_ingredient_substrings: list[str] = Field(default_factory=list)
    strict: bool = True


class Preferences(BaseModel):
    disliked_ingredient_substrings: list[str] = Field(default_factory=list)


class PlanningDefaults(BaseModel):
    prep_buffer_minutes: int = 10
    default_slot_minutes_if_no_calendar: int = 45


class UserProfile(BaseModel):
    user_id: str = "local"
    timezone: str = "Europe/Moscow"
    goal_calories_per_day: int | None = None
    goal_protein_g_per_day: int | None = None
    restrictions: Restrictions = Field(default_factory=Restrictions)
    preferences: Preferences = Field(default_factory=Preferences)
    servings: int = 2
    meals_per_day: int = 3
    meal_types: list[str] = Field(
        default_factory=lambda: ["Breakfast", "Lunch", "Dinner"]
    )
    equipment: list[str] = Field(default_factory=list)
    week_anchor_date: date
    planning_defaults: PlanningDefaults = Field(default_factory=PlanningDefaults)


class TimeWindow(BaseModel):
    start: str
    end: str


class CalendarFreeBusy(BaseModel):
    free: list[TimeWindow] = Field(default_factory=list)


class CookWindow(BaseModel):
    start: str
    end: str


class SourceRef(BaseModel):
    link: str = ""


class PlannedMeal(BaseModel):
    slot_id: str
    meal_type: str
    recipe_id: str
    title: str
    ready_minutes: int
    cook_window: CookWindow
    source_ref: SourceRef = Field(default_factory=SourceRef)


class PlanDay(BaseModel):
    date: str
    meals: list[PlannedMeal] = Field(default_factory=list)


class PlanMeta(BaseModel):
    pipeline_version: str = "0.1.0"
    reason_codes: list[str] = Field(default_factory=list)


class WeeklyPlan(BaseModel):
    week_start: str
    days: list[PlanDay] = Field(default_factory=list)
    meta: PlanMeta = Field(default_factory=PlanMeta)


class ValidatePlanResult(BaseModel):
    valid: bool
    reason_codes: list[str] = Field(default_factory=list)


class GetRecipesResult(BaseModel):
    items: list[RecipeCard] = Field(default_factory=list)
    error: str | None = None
    code: str | None = None


class ReplanTrigger(BaseModel):
    trigger: Literal["missed_meal", "calendar_change", "ingredient_unavailable"]
    affected_dates: list[str] = Field(default_factory=list)
    meal_slot_ids: list[str] | None = None
    notes: str | None = None


class ShoppingLine(BaseModel):
    product: str
    qty: float | None = None
    unit: str = ""
    category: str | None = None
    already_have: bool = False


class ShoppingListResult(BaseModel):
    lines: list[ShoppingLine] = Field(default_factory=list)
    error: str | None = None
    code: str | None = None


class InventoryItem(BaseModel):
    name_normalized: str
    qty: float | None = None
    unit: str | None = None
