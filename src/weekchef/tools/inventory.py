"""Tool: inventory_get / inventory_update."""

from __future__ import annotations

from psycopg import Connection

from weekchef.db import inventory as inv_db
from weekchef.schemas import InventoryItem


def inventory_get(conn: Connection, user_key: str) -> list[InventoryItem]:
    rows = inv_db.inventory_list(conn, user_key)
    return [InventoryItem.model_validate(r) for r in rows]


def inventory_update(
    conn: Connection,
    user_key: str,
    items: list[InventoryItem],
) -> None:
    inv_db.inventory_clear(conn, user_key)
    for it in items:
        inv_db.inventory_upsert(
            conn,
            user_key,
            it.name_normalized,
            it.qty,
            it.unit,
        )
