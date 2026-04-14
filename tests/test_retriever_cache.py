"""Retriever cache key and TTL behavior."""

import time

from weekchef.schemas import GetRecipesResult, RecipeCard, RecipeFilters
from weekchef.tools.retriever_cache import InMemoryRetrieverCache, retriever_cache_key


def test_cache_key_stable_for_equivalent_filters() -> None:
    a = RecipeFilters(max_ready_minutes=30, banned_ingredient_substrings=["milk"])
    b = RecipeFilters(max_ready_time=30, banned_ingredient_substrings=["milk"])
    assert retriever_cache_key("t", a, 20) == retriever_cache_key("t", b, 20)


def test_cache_key_differs_by_table_or_limit() -> None:
    f = RecipeFilters()
    assert retriever_cache_key("a", f, 10) != retriever_cache_key("b", f, 10)
    assert retriever_cache_key("t", f, 10) != retriever_cache_key("t", f, 11)


def test_cache_ttl_expires() -> None:
    c = InMemoryRetrieverCache()
    f = RecipeFilters()
    k = retriever_cache_key("t", f, 5)
    card = RecipeCard(id=1, name="x")
    c.set(k, GetRecipesResult(items=[card]), ttl_seconds=0.05)
    assert c.get(k) is not None
    time.sleep(0.08)
    assert c.get(k) is None


def test_cache_skips_errors() -> None:
    c = InMemoryRetrieverCache()
    k = "k"
    c.set(k, GetRecipesResult(error="x", code="DB_ERROR"), ttl_seconds=60.0)
    assert c.get(k) is None
