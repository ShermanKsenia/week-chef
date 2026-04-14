"""OpenTelemetry: in-memory exporter and dialogue attributes on root span."""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weekchef.observability.context import request_context
from weekchef.observability.spans import user_turn_root_span


def test_user_turn_span_has_dialogue_attributes():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    try:
        with request_context(
            correlation_id="cid-1",
            user_key="tg:99",
            dialogue_id="dlg-uuid",
            turn_index=3,
        ):
            with user_turn_root_span():
                pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        s = spans[0]
        assert s.name == "user_turn"
        attrs = dict(s.attributes or {})
        assert attrs.get("weekchef.correlation_id") == "cid-1"
        assert attrs.get("weekchef.user_id") == "tg:99"
        assert attrs.get("weekchef.dialogue_id") == "dlg-uuid"
        assert attrs.get("weekchef.turn_index") == 3
    finally:
        trace.set_tracer_provider(TracerProvider())
