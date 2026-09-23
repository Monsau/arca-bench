"""Prometheus /metrics instrumentation for the external observability stack.

Observability standard (Gartner-style + Zero Trust): every Arca Suite module
exposes a Prometheus text-format endpoint so the cluster observability stack
can scrape it. /metrics is intentionally UNAUTHENTICATED — it is exposed
cluster-internally only, and NetworkPolicy restricts scraping to the
observability pods (that policy is managed outside this module).
"""
import time

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    Info,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match

MODULE_NAME = "arca-bench"
MODULE_VERSION = "0.1.5"

REQUEST_COUNT = Counter(
    "arca_http_requests_total",
    "HTTP requests, by route template, method and status code.",
    ["route", "method", "status"],
)
REQUEST_LATENCY = Histogram(
    "arca_http_request_duration_seconds",
    "HTTP request latency in seconds, by route template and method.",
    ["route", "method"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
MODULE_INFO = Info(
    "arca_module",
    "Arca Suite module identity: name and release version.",
)
MODULE_INFO.info({"module": MODULE_NAME, "version": MODULE_VERSION})


def metrics_response() -> Response:
    """Render the default registry in Prometheus text exposition format."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _route_template(request: Request) -> str:
    """Resolve the low-cardinality route template for a matched request.

    API routes label by their path template (e.g. /api/v1/runs/{run_id}),
    never by the raw URL path, so path parameters cannot explode the label
    cardinality.
    """
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    for candidate in request.app.routes:
        match, _ = candidate.matches(request.scope)
        if match == Match.FULL:
            return getattr(candidate, "path", None) or request.url.path
    return request.url.path


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Record request count and latency per route template + status code."""

    async def dispatch(self, request: Request, call_next):
        # Scrapes of /metrics itself are not recorded: they would add
        # scrape-driven noise rather than service-traffic signal.
        if request.url.path == "/metrics":
            return await call_next(request)
        method = request.method
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            duration = time.perf_counter() - start
            route = _route_template(request)
            REQUEST_COUNT.labels(route, method, str(status)).inc()
            REQUEST_LATENCY.labels(route, method).observe(duration)
