"""Load and validate user profile JSON."""

from __future__ import annotations

import json
from pathlib import Path

from psycopg import Connection

from weekchef.schemas import UserProfile


def load_profile(path: Path) -> UserProfile:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    return UserProfile.model_validate(data)


def parse_profile_dict(data: dict) -> UserProfile:
    return UserProfile.model_validate(data)


def load_or_seed_profile(conn: Connection, user_key: str, seed_path: Path) -> UserProfile:
    """Read profile from ``weekchef_profiles`` or copy ``seed_path`` once and persist."""
    from weekchef.db.profiles import profile_get, profile_upsert

    raw = profile_get(conn, user_key)
    if raw:
        return UserProfile.model_validate(raw)
    base = load_profile(seed_path).model_copy(update={"user_id": user_key})
    profile_upsert(conn, user_key, base)
    return base


def telegram_user_key(telegram_user_id: int) -> str:
    return f"tg:{telegram_user_id}"
