"""Synchronous PostgreSQL connections (CLI and scripts)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import Connection


@contextmanager
def sync_connection(dsn: str) -> Iterator[Connection]:
    conn = psycopg.connect(dsn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
