"""Unit and service tests for arca-bench."""
import os

import pytest

from src.core.domain.test_models import Score, TestCase, TestResult, TestRun
from src.core.events.bench_events import OutboxPublisher
from src.core.security.jwt import create_access_token, verify_token
from src.core.services.bench_service import BenchService
from src.infra.soc import EmbeddedSOC
from src.infra.store import SqlBenchRepository, connect_sqlite


@pytest.fixture
def service():
    repo = SqlBenchRepository(connect_sqlite())
    publisher = OutboxPublisher()
    soc = EmbeddedSOC()
    return BenchService(repo, publisher, soc=soc), publisher, soc


def test_register_test():
    repo = SqlBenchRepository(connect_sqlite())
    svc = BenchService(repo)
    test = svc.register_test("provenance", "semantic")
    assert test.category == "semantic"
    assert svc.list_tests()


def test_run_lifecycle(service):
    svc, publisher, _ = service
    t = svc.register_test("t1", "security")
    run = svc.start_run("arca-flow", [t.id])
    assert run.status.value == "started"
    svc.submit_result(run.id, t.id, True, "ok")
    summary = svc.complete_run(run.id)
    assert summary["passed"] == 1
    assert summary["failed"] == 0
    assert summary["scores"]
    assert summary["scorecard"]["overall"] == 1.0
    topics = [e.topic for e in publisher.drain()]
    assert "bench.run.started" in topics
    assert "bench.run.completed" in topics
    assert "bench.score.published" in topics


def test_score_computed_by_category(service):
    svc, _, _ = service
    t1 = svc.register_test("t1", "security")
    t2 = svc.register_test("t2", "security")
    t3 = svc.register_test("t3", "semantic")
    run = svc.start_run("target", [t1.id, t2.id, t3.id])
    svc.submit_result(run.id, t1.id, True)
    svc.submit_result(run.id, t2.id, False)
    svc.submit_result(run.id, t3.id, True)
    summary = svc.complete_run(run.id)
    scores = {s["dimension"]: s["value"] for s in summary["scores"]}
    assert scores["security"] == 0.5
    assert scores["semantic"] == 1.0


def test_fail_run(service):
    svc, publisher, _ = service
    t = svc.register_test("t1", "security")
    run = svc.start_run("target", [t.id])
    svc.fail_run(run.id, "runner crashed")
    events = publisher.drain()
    assert any(e.topic == "bench.run.completed" for e in events)
    with pytest.raises(ValueError):
        svc.complete_run(run.id)


def test_result_after_completion_rejected(service):
    svc, _, _ = service
    t = svc.register_test("t1", "security")
    run = svc.start_run("target", [t.id])
    svc.submit_result(run.id, t.id, True)
    svc.complete_run(run.id)
    with pytest.raises(ValueError):
        svc.submit_result(run.id, t.id, True)


def test_score_value_range():
    with pytest.raises(ValueError):
        Score(target="x", dimension="d", value=1.5, run_id="r")


def test_store_roundtrip():
    repo = SqlBenchRepository(connect_sqlite())
    run = TestRun(target="x", suite=["a"])
    repo.save_run(run)
    loaded = repo.get_run(run.id)
    assert loaded.target == run.target
    assert loaded.suite == ["a"]


def test_evidence_collection(service):
    svc, publisher, _ = service
    t = svc.register_test("t1", "performance")
    run = svc.start_run("target", [t.id])
    ev = svc.collect_evidence(run.id, "https://example.com/log", b"log-data")
    assert ev.sha256
    assert svc.list_evidence(run.id)
    assert any(e.topic == "bench.evidence.collected" for e in publisher.drain())


def test_report_generation(service):
    svc, publisher, _ = service
    t = svc.register_test("t1", "security")
    run = svc.start_run("target", [t.id])
    svc.submit_result(run.id, t.id, False, "failed")
    svc.complete_run(run.id)
    report = svc.generate_report(run.id, "json")
    assert report.format == "json"
    assert "remediations" in report.content
    assert any(e.topic == "bench.report.generated" for e in publisher.drain())


def test_soc_audit_collected(service):
    svc, _, soc = service
    t = svc.register_test("t1", "security")
    run = svc.start_run("target", [t.id])
    svc.submit_result(run.id, t.id, True)
    svc.complete_run(run.id)
    events = soc.collector.events()
    assert any(e["type"] == "operation_started" for e in events)
    assert any(e["type"] == "run_completed" for e in events)


def test_jwt_dev_mode():
    os.environ["BENCH_JWT_SECRET"] = "test-secret"
    if "BENCH_AUTH_DISABLED" in os.environ:
        del os.environ["BENCH_AUTH_DISABLED"]
    token = create_access_token({"sub": "user1", "roles": ["bench_runner"]},
                                "test-secret")
    payload = verify_token(token)
    assert payload["sub"] == "user1"
    assert "bench_runner" in payload["roles"]
