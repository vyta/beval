"""OpenTelemetry tracing setup for the beval framework.

Provides tracing configuration for process graders that inspect execution
traces. See SPEC.md §9 (Process Graders via Traces).
"""

from __future__ import annotations

from typing import Any

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory import (
        InMemorySpanExporter,
    )

    _HAS_OTEL = True
except ImportError:
    _HAS_OTEL = False

_MISSING_MSG = (
    "OpenTelemetry is required for tracing. "
    "Install with: pip install 'beval[tracing]'"
)


def setup_tracing(*, service_name: str = "beval") -> Any:
    """Configure OpenTelemetry tracing with an in-memory exporter.

    Returns the exporter so process graders can inspect captured spans.

    Raises:
        ImportError: If OpenTelemetry is not installed.
    """
    if not _HAS_OTEL:
        raise ImportError(_MISSING_MSG)
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return exporter


def get_tracer(name: str = "beval") -> Any:
    """Get a tracer instance from the current provider.

    Raises:
        ImportError: If OpenTelemetry is not installed.
    """
    if not _HAS_OTEL:
        raise ImportError(_MISSING_MSG)
    return trace.get_tracer(name)
