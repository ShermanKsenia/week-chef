"""Request context (contextvars + structlog bind)."""

from __future__ import annotations

import structlog.contextvars

from weekchef.observability.context import get_correlation_id, request_context
from weekchef.observability.logging_setup import configure_logging


def setup_module() -> None:
    configure_logging(json_logs=False, log_level="DEBUG")


def test_request_context_restores_correlation_id():
    assert get_correlation_id() is None
    with request_context(correlation_id="outer", user_key="tg:1", dialogue_id="d1", turn_index=1):
        assert get_correlation_id() == "outer"
        with request_context(correlation_id="inner", user_key="tg:2", dialogue_id="d2", turn_index=2):
            assert get_correlation_id() == "inner"
        assert get_correlation_id() == "outer"
    assert get_correlation_id() is None
    structlog.contextvars.clear_contextvars()
