"""Application DB helpers (OAuth tokens, etc.)."""

from __future__ import annotations

from typing import Any

from psycopg import Connection
from psycopg.types.json import Json


def oauth_token_get(conn: Connection, user_key: str) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT token_json FROM weekchef_oauth_tokens WHERE user_key = %s",
            (user_key,),
        )
        row = cur.fetchone()
    if not row:
        return None
    raw = row[0]
    if isinstance(raw, dict):
        return raw
    return dict(raw)


def oauth_token_save(conn: Connection, user_key: str, token: dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO weekchef_oauth_tokens (user_key, token_json, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (user_key) DO UPDATE SET
                token_json = EXCLUDED.token_json,
                updated_at = NOW()
            """,
            (user_key, Json(token)),
        )
