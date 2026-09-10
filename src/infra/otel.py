"""OpenTelemetry instrumentation: traces, metrics, logs."""
import logging

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    _OTEL_AVAILABLE = False

from ..config import settings


def instrument(app):
    """Wire OTel into the FastAPI app. No-op when the SDK is not installed."""
    logging.basicConfig(level=settings.log_level)
    if not _OTEL_AVAILABLE:
        return
    resource = Resource.create({"service.name": settings.app_name})
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)
