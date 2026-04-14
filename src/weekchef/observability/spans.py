"""Small helpers around OTel spans."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from weekchef.observability.context import otel_common_attributes
from weekchef.observability.otel import get_tracer


@contextmanager
def phase_span(name: str, extra_attrs: dict[str, Any] | None = None) -> Iterator[Any]:
    """Pipeline phase span (INTAKE, ENRICH, …)."""
    attrs = {**otel_common_attributes(), "weekchef.phase": name}
    if extra_attrs:
        attrs.update(extra_attrs)
    tracer = get_tracer("weekchef.pipeline")
    with tracer.start_as_current_span(name, attributes=attrs) as span:
        try:
            yield span
        except Exception:
            span.set_attribute("error", True)
            raise


@contextmanager
def user_turn_root_span() -> Iterator[Any]:
    """Root span for ``process_user_turn`` (one message / trace)."""
    attrs = {**otel_common_attributes(), "weekchef.span.kind": "user_turn"}
    tracer = get_tracer("weekchef.orchestrator_turn")
    with tracer.start_as_current_span("user_turn", attributes=attrs) as span:
        try:
            yield span
        except Exception:
            span.set_attribute("error", True)
            raise
