"""Redaction helpers — no raw user text in logs (governance)."""

from __future__ import annotations

import hashlib


def intake_text_hash(text: str, *, length: int = 16) -> str:
    """Short stable hash for correlating events without storing raw intake."""
    raw = (text or "").encode("utf-8", errors="replace")
    h = hashlib.sha256(raw).hexdigest()
    return h[: max(8, min(length, len(h)))]
