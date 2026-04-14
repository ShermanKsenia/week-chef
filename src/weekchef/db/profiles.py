"""Persist ``UserProfile`` JSON in ``weekchef_profiles``."""

from __future__ import annotations

from typing import Any

from psycopg import Connection
from psycopg.types.json import Json

from weekchef.schemas import UserProfile


def profile_get(conn: Connection, user_key: str) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT profile_json FROM weekchef_profiles WHERE user_key = %s",
            (user_key,),
        )
        row = cur.fetchone()
    if not row:
        return None
    raw = row[0]
    return dict(raw) if isinstance(raw, dict) else {}


def profile_upsert(conn: Connection, user_key: str, profile: UserProfile) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO weekchef_profiles (user_key, profile_json, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (user_key) DO UPDATE SET
                profile_json = EXCLUDED.profile_json,
                updated_at = NOW()
            """,
            (user_key, Json(profile.model_dump(mode="json"))),
        )
