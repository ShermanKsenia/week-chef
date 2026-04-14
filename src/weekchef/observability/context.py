"""Request-scoped context (correlation, user, dialogue) for logs and traces."""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Any, Iterator

import structlog.contextvars

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("wc_correlation_id", default=None)
_user_key: contextvars.ContextVar[str | None] = contextvars.ContextVar("wc_user_key", default=None)
_dialogue_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("wc_dialogue_id", default=None)
_turn_index: contextvars.ContextVar[int | None] = contextvars.ContextVar("wc_turn_index", default=None)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def get_user_key() -> str | None:
    return _user_key.get()


def get_dialogue_id() -> str | None:
    return _dialogue_id.get()


def get_turn_index() -> int | None:
    return _turn_index.get()


def otel_common_attributes() -> dict[str, Any]:
    """Attributes safe to attach to root/child spans (no user text)."""
    out: dict[str, Any] = {}
    cid = get_correlation_id()
    if cid:
        out["weekchef.correlation_id"] = cid
    uk = get_user_key()
    if uk:
        out["weekchef.user_id"] = uk
    did = get_dialogue_id()
    if did:
        out["weekchef.dialogue_id"] = did
    ti = get_turn_index()
    if ti is not None:
        out["weekchef.turn_index"] = ti
    return out


@contextmanager
def request_context(
    *,
    correlation_id: str,
    user_key: str | None = None,
    dialogue_id: str | None = None,
    turn_index: int | None = None,
) -> Iterator[None]:
    """Bind context for one request / user turn (restores previous values on exit)."""
    tok_c = _correlation_id.set(correlation_id)
    tok_u = _user_key.set(user_key) if user_key is not None else None
    tok_d = _dialogue_id.set(dialogue_id) if dialogue_id is not None else None
    tok_t = _turn_index.set(turn_index) if turn_index is not None else None
    log_bind: dict[str, Any] = {"correlation_id": correlation_id}
    if user_key is not None:
        log_bind["user_id"] = user_key
    if dialogue_id is not None:
        log_bind["dialogue_id"] = dialogue_id
    if turn_index is not None:
        log_bind["turn_index"] = turn_index
    structlog.contextvars.bind_contextvars(**log_bind)
    try:
        yield
    finally:
        structlog.contextvars.unbind_contextvars(*list(log_bind.keys()))
        _correlation_id.reset(tok_c)
        if tok_u is not None:
            _user_key.reset(tok_u)
        if tok_d is not None:
            _dialogue_id.reset(tok_d)
        if tok_t is not None:
            _turn_index.reset(tok_t)
