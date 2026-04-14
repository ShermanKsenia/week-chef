"""Structlog configuration (JSON or console)."""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(*, json_logs: bool, log_level: str = "INFO") -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level, force=True)

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
    ]
    if json_logs:
        shared.append(structlog.processors.JSONRenderer())
    else:
        shared.append(structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()))

    structlog.configure(
        processors=shared,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "weekchef"):
    return structlog.get_logger(name)
