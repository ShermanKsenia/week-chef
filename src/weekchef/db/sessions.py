"""Telegram session state in ``weekchef_sessions``."""

from __future__ import annotations

from typing import Any

from psycopg import Connection
from psycopg.types.json import Json


def session_get(conn: Connection, telegram_user_id: int) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT state_json FROM weekchef_sessions WHERE telegram_user_id = %s",
            (telegram_user_id,),
        )
        row = cur.fetchone()
    if not row:
        return {}
    raw = row[0]
    return dict(raw) if isinstance(raw, dict) else {}


def session_upsert(conn: Connection, telegram_user_id: int, state: dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO weekchef_sessions (telegram_user_id, state_json)
            VALUES (%s, %s)
            ON CONFLICT (telegram_user_id) DO UPDATE SET
                state_json = EXCLUDED.state_json,
                updated_at = NOW()
            """,
            (telegram_user_id, Json(state)),
        )
