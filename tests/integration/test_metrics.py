"""Prometheus /metrics observability surface.

Standard: /metrics serves Prometheus text format for the external
observability cluster; the endpoint is UNAUTHENTICATED (cluster-internal
exposure via NetworkPolicy) and therefore must stay OUTSIDE the
docs/metadata JWT gate, which only covers /docs, /redoc and /openapi.json.
"""
from fastapi.testclient import TestClient

from src.config import settings
from src.main import app

client = TestClient(app)


def test_metrics_serves_prometheus_text_format():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "# HELP" in response.text


def test_metrics_exposes_module_identity():
    response = client.get("/metrics")
    assert 'arca_module_info{module="arca-bench",version="0.1.5"}' in response.text


def test_metrics_not_behind_docs_metadata_gate(monkeypatch):
    # In production the docs/metadata routes require a JWT, but /metrics must
    # remain open for the in-cluster observability scraper (NetworkPolicy
    # protects it) — no other route's auth is weakened.
    monkeypatch.setattr(settings, "environment", "production")
    assert client.get("/docs").status_code == 401
    assert client.get("/metrics").status_code == 200


def test_middleware_counts_request_by_route_template():
    # Route templates, not raw paths: a parameterized request must label the
    # counter with the template (no cardinality explosion from path params).
    probe = client.get("/api/v1/runs/run-probe-123")
    assert probe.status_code in (200, 401, 403)
    response = client.get("/metrics")
    assert (
        'arca_http_requests_total{method="GET",route="/api/v1/runs/{run_id}",status="'
        in response.text
    )
    assert "run-probe-123" not in response.text.split("arca_http_requests_total")[1].split("# HELP")[0]


def test_middleware_records_latency_histogram():
    client.get("/healthz")
    response = client.get("/metrics")
    assert (
        'arca_http_request_duration_seconds_count{method="GET",route="/healthz"}'
        in response.text
    )
