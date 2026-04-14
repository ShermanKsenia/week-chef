"""OTel metrics helpers (reload module so instruments bind to test MeterProvider)."""

from __future__ import annotations

import importlib

import pytest
from opentelemetry import metrics as api_metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader


def _metric_names(reader: InMemoryMetricReader) -> set[str]:
    md = reader.get_metrics_data()
    if md is None:
        return set()
    names: set[str] = set()
    for rm in md.resource_metrics:
        for sm in rm.scope_metrics:
            for metric in sm.metrics:
                names.add(metric.name)
    return names


@pytest.fixture
def metrics_module():
    """Fresh ``weekchef.observability.metrics`` bound to an in-memory OTel metrics export.

    OpenTelemetry allows only one ``MeterProvider`` replacement per process; keep
    all assertions in a single test that uses this fixture.
    """
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    previous = api_metrics.get_meter_provider()
    api_metrics.set_meter_provider(provider)
    import weekchef.observability.metrics as m

    importlib.reload(m)
    try:
        yield reader, m
    finally:
        api_metrics.set_meter_provider(previous)
        importlib.reload(m)


def test_custom_metrics_export_to_reader(metrics_module):
    reader, m = metrics_module
    m.inc_llm_unavailable(step="parse_input", reason="nonrecoverable")
    m.inc_llm_fallback_model(step="parse_input")
    m.record_validate_duration_ms(15.0)
    names = _metric_names(reader)
    assert "weekchef.llm.unavailable" in names
    assert "weekchef.llm.fallback_model_calls" in names
    assert "weekchef.validate.duration_ms" in names
