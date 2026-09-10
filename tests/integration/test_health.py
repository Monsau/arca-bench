"""Integration test: the application boots and answers /healthz."""
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from src.main import app  # noqa: E402


def test_healthz():
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_v1_health():
    client = TestClient(app)
    response = client.get("/api/v1/bench/health")
    assert response.status_code == 200
