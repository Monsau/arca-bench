"""Unit and service tests for arca-bench."""
import pytest

from src.core.domain.test_models import Score, TestCase, TestResult, TestRun
from src.core.events.bench_events import OutboxPublisher
from src.core.services.bench_service import BenchService
from src.infra.store import SqlBenchRepository, connect_sqlite


@pytest.fixture
def service():
    repo = SqlBenchRepository(connect_sqlite())
    publisher = OutboxPublisher()
    return BenchService(repo, publisher), publisher


def test_register_test():
    repo = SqlBenchRepository(connect_sqlite())
    svc = BenchService(repo)
    test = svc.register_test("provenance", "semantic")
    assert test.category == "semantic"
    assert svc.list_tests()


def test_run_lifecycle(service):
    svc, publisher = service
    t = svc.register_test("t1", "security")
    run = svc.start_run("arca-flow", [t.id])
    assert run.status.value == "started"
    svc.submit_result(run.id, t.id, True, "ok")
    summary = svc.complete_run(run.id)
    assert summary["passed"] == 1
    assert summary["failed"] == 0
    assert summary["scores"]
    topics = [e.topic for e in publisher.drain()]
    assert "bench.run.started" in topics
    assert "bench.run.completed" in topics
    assert "bench.score.published" in topics


def test_score_computed_by_category(service):
    svc, _ = service
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
    svc, publisher = service
    t = svc.register_test("t1", "security")
    run = svc.start_run("target", [t.id])
    svc.fail_run(run.id, "runner crashed")
    events = publisher.drain()
    assert any(e.topic == "bench.run.completed" for e in events)
    with pytest.raises(ValueError):
        svc.complete_run(run.id)


def test_result_after_completion_rejected(service):
    svc, _ = service
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
