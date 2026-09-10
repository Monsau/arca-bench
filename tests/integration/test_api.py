"""Integration tests for arca-bench REST and MCP."""
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from src.main import app  # noqa: E402


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_healthz(client):
    assert client.get("/healthz").json()["status"] == "ok"


def test_full_run_rest(client):
    test = client.post("/api/v1/tests", json={"name": "prov",
                                              "category": "semantic"}).json()
    run = client.post("/api/v1/runs", json={"target": "arca-flow",
                                            "suite": [test["id"]]}).json()
    res = client.post(f"/api/v1/runs/{run['run_id']}/results",
                      json={"test_case_id": test["id"], "passed": True,
                            "details": "ok"})
    assert res.status_code == 201
    summary = client.post(f"/api/v1/runs/{run['run_id']}/complete").json()
    assert summary["passed"] == 1
    scores = client.get("/api/v1/scores", params={"target": "arca-flow"}).json()
    assert scores["scores"]


def test_mcp_test_run(client):
    test = client.post("/mcp/tools/test-register",
                       json={"name": "t", "category": "c"}).json()
    run = client.post("/mcp/tools/test-run",
                      json={"target": "x", "suite": [test["id"]]}).json()
    assert run["run_id"]


def test_mcp_score_compute(client):
    test = client.post("/mcp/tools/test-register",
                       json={"name": "t2", "category": "c"}).json()
    run = client.post("/mcp/tools/test-run",
                      json={"target": "y", "suite": [test["id"]]}).json()
    client.post(f"/api/v1/runs/{run['run_id']}/results",
                json={"test_case_id": test["id"], "passed": True})
    client.post(f"/api/v1/runs/{run['run_id']}/complete")
    scores = client.post("/mcp/tools/score-compute",
                         json={"target": "y"}).json()
    assert scores["scores"]
