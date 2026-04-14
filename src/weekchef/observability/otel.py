"""OpenTelemetry tracer and meter providers (OTLP or console)."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from weekchef.config import Settings

if TYPE_CHECKING:
    from opentelemetry.trace import Tracer

_tracing_configured = False
_metrics_configured = False
_log = logging.getLogger("weekchef.observability")


def configure_tracing(settings: Settings) -> None:
    """Idempotent: set global TracerProvider when ``settings.otel_enabled``."""
    global _tracing_configured
    if not settings.otel_enabled or _tracing_configured:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    except ImportError as e:  # pragma: no cover
        _log.warning("OpenTelemetry SDK not installed: %s", e)
        return

    resource = Resource.create(
        {
            "service.name": (os.environ.get("OTEL_SERVICE_NAME") or "weekchef").strip(),
            "service.version": settings.pipeline_version,
        }
    )
    provider = TracerProvider(resource=resource)
    if settings.otel_traces_console:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        except ImportError as e:  # pragma: no cover
            _log.warning("OTLP HTTP trace exporter not available: %s", e)

    trace.set_tracer_provider(provider)
    _tracing_configured = True


def configure_metrics(settings: Settings) -> None:
    global _metrics_configured
    if not settings.otel_enabled or _metrics_configured:
        return
    try:
        from opentelemetry import metrics
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
    except ImportError as e:  # pragma: no cover
        _log.warning("OpenTelemetry metrics not available: %s", e)
        return

    resource = Resource.create({"service.name": (os.environ.get("OTEL_SERVICE_NAME") or "weekchef").strip()})
    readers: list = []
    if settings.otel_metrics_console:
        readers.append(PeriodicExportingMetricReader(ConsoleMetricExporter(), export_interval_millis=60_000))
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        try:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

            readers.append(
                PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=60_000),
            )
        except ImportError as e:  # pragma: no cover
            _log.warning("OTLP HTTP metric exporter not available: %s", e)
    if not readers:
        return
    provider = MeterProvider(resource=resource, metric_readers=readers)
    metrics.set_meter_provider(provider)
    _metrics_configured = True


def get_tracer(name: str = "weekchef") -> "Tracer":
    try:
        from opentelemetry import trace

        return trace.get_tracer(name, None)
    except ImportError:  # pragma: no cover
        from opentelemetry.trace import NoOpTracer

        return NoOpTracer()


def get_meter(name: str = "weekchef"):
    try:
        from opentelemetry import metrics

        return metrics.get_meter(name, None)
    except ImportError:  # pragma: no cover
        return _NoOpMeter()


class _NoOpMeter:  # pragma: no cover
    def create_histogram(self, *args: object, **kwargs: object):
        return _NoOpInstrument()

    def create_counter(self, *args: object, **kwargs: object):
        return _NoOpInstrument()


class _NoOpInstrument:  # pragma: no cover
    def record(self, *args: object, **kwargs: object) -> None:
        return None

    def add(self, *args: object, **kwargs: object) -> None:
        return None
