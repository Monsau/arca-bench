"""Integration tests for arca-bench REST, GraphQL and MCP."""
import os

import pytest

os.environ.setdefault("BENCH_AUTH_DISABLED", "1")

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
    scorecard = client.get(f"/api/v1/scorecards/{run['run_id']}").json()
    assert scorecard["overall"] == 1.0
    report = client.get(f"/api/v1/runs/{run['run_id']}/report",
                        params={"format": "json"}).json()
    assert report["format"] == "json"


def test_evidence_rest(client):
    test = client.post("/api/v1/tests", json={"name": "ev",
                                              "category": "semantic"}).json()
    run = client.post("/api/v1/runs", json={"target": "x",
                                            "suite": [test["id"]]}).json()
    ev = client.post(f"/api/v1/runs/{run['run_id']}/evidence",
                     json={"artifact_url": "https://example.com/artifact",
                           "content": "evidence payload"}).json()
    assert ev["sha256"]
    listed = client.get(f"/api/v1/runs/{run['run_id']}/evidence").json()
    assert listed["evidence"]


def test_mcp_run_test_suite(client):
    test = client.post("/mcp/tools/test-register",
                       json={"name": "t", "category": "c"}).json()
    result = client.post("/mcp/tools/run_test_suite",
                         json={"target": "x", "suite": [test["id"]]}).json()
    assert result["run_id"]
    assert result["summary"]["passed"] == 1


def test_mcp_get_scorecard(client):
    result = client.post("/mcp/tools/run_test_suite",
                         json={"target": "y", "suite": []}).json()
    scorecard = client.post("/mcp/tools/get_scorecard",
                            json={"run_id": result["run_id"]}).json()
    assert "overall" in scorecard


def test_mcp_generate_report(client):
    test = client.post("/mcp/tools/test-register",
                       json={"name": "t2", "category": "c"}).json()
    result = client.post("/mcp/tools/run_test_suite",
                         json={"target": "z", "suite": [test["id"]]}).json()
    report = client.post("/mcp/tools/generate_report",
                         json={"run_id": result["run_id"], "format": "html"}).json()
    assert report["format"] == "html"


def test_graphql_roundtrip(client):
    resp = client.post("/graphql", json={
        "query": 'mutation { registerTest(name: "gql", category: "perf") { id name category } }'
    })
    assert resp.status_code == 200
    data = resp.json()["data"]["registerTest"]
    test_id = data["id"]

    resp = client.post("/graphql", json={
        "query": f'mutation {{ startRun(target: "gql-target", suite: ["{test_id}"]) {{ id status }} }}'
    })
    run_id = resp.json()["data"]["startRun"]["id"]

    resp = client.post("/graphql", json={
        "query": f'query {{ run(id: "{run_id}") {{ target status }} }}'
    })
    assert resp.json()["data"]["run"]["target"] == "gql-target"
