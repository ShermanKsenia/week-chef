"""In-memory retriever result cache (24h TTL by default; key = stable filter hash)."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any

from weekchef.schemas import GetRecipesResult, RecipeFilters


def retriever_cache_key(table_name: str, filters: RecipeFilters, limit: int) -> str:
    """Stable key for ``(table, filters, limit)`` (matches retriever spec: hash of filters)."""
    payload: dict[str, Any] = {
        "table": table_name,
        "limit": limit,
        "filters": filters.model_dump(mode="json"),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class InMemoryRetrieverCache:
    """Thread-safe TTL cache for successful ``GetRecipesResult`` only."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, dict[str, Any]]] = {}

    def _purge_unlocked(self, now: float) -> None:
        dead = [k for k, (exp, _) in self._store.items() if exp <= now]
        for k in dead:
            del self._store[k]

    def get(self, key: str) -> GetRecipesResult | None:
        now = time.time()
        with self._lock:
            self._purge_unlocked(now)
            hit = self._store.get(key)
            if not hit:
                return None
            exp, data = hit
            if exp <= now:
                del self._store[key]
                return None
            return GetRecipesResult.model_validate(data)

    def set(self, key: str, result: GetRecipesResult, ttl_seconds: float) -> None:
        if result.error or result.code:
            return
        now = time.time()
        with self._lock:
            self._purge_unlocked(now)
            self._store[key] = (now + ttl_seconds, result.model_dump(mode="json"))

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_GLOBAL = InMemoryRetrieverCache()


def global_retriever_cache() -> InMemoryRetrieverCache:
    return _GLOBAL
