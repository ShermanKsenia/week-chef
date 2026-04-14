"""Inventory CRUD in PostgreSQL."""

from __future__ import annotations

from typing import Any

from psycopg import Connection


def inventory_list(conn: Connection, user_key: str) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT name_normalized, qty, unit
            FROM weekchef_inventory
            WHERE user_key = %s
            ORDER BY name_normalized
            """,
            (user_key,),
        )
        rows = cur.fetchall()
    return [
        {"name_normalized": r[0], "qty": float(r[1]) if r[1] is not None else None, "unit": r[2]}
        for r in rows
    ]


def inventory_upsert(
    conn: Connection,
    user_key: str,
    name_normalized: str,
    qty: float | None,
    unit: str | None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO weekchef_inventory (user_key, name_normalized, qty, unit)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_key, name_normalized) DO UPDATE SET
                qty = EXCLUDED.qty,
                unit = EXCLUDED.unit
            """,
            (user_key, name_normalized, qty, unit),
        )


def inventory_delete(conn: Connection, user_key: str, name_normalized: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM weekchef_inventory WHERE user_key = %s AND name_normalized = %s",
            (user_key, name_normalized),
        )


def inventory_clear(conn: Connection, user_key: str) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM weekchef_inventory WHERE user_key = %s", (user_key,))
