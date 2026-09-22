"""Unit and service tests for arca-bench."""
import os

import pytest

from src.core.domain.test_models import Score, TestCase, TestResult, TestRun
from src.core.events.bench_events import OutboxPublisher
from src.core.security.jwt import verify_token
from src.core.services.bench_service import BenchService
from src.infra.soc import EmbeddedSOC
from src.infra.store import SqlBenchRepository, connect_sqlite

from tests.oidc_test_utils import (
    TEST_AUDIENCE,
    TEST_ISSUER,
    generate_keypair,
    install_test_jwks,
    mint_test_token,
)


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


def test_jwt_rs256_against_test_jwks():
    """verify_token checks RS256 signatures against the realm JWKS — the same
    strict path as production, exercised with a generated test keypair."""
    os.environ["BENCH_OIDC_JWKS_URL"] = "test-jwks"
    os.environ["BENCH_OIDC_ISSUER"] = TEST_ISSUER
    os.environ["BENCH_OIDC_AUDIENCE"] = TEST_AUDIENCE
    private_key, _ = generate_keypair()
    install_test_jwks(private_key)
    token = mint_test_token(private_key, "user1", ["bench_runner"])
    payload = verify_token(token)
    assert payload["sub"] == "user1"
    assert "bench_runner" in payload["roles"]


def test_jwt_rejects_hs256_and_bad_signatures():
    """Security by design: symmetric HS256 tokens and wrong keys are refused."""
    from jose import jwt as jose_jwt

    os.environ["BENCH_OIDC_JWKS_URL"] = "test-jwks"
    os.environ["BENCH_OIDC_ISSUER"] = TEST_ISSUER
    os.environ["BENCH_OIDC_AUDIENCE"] = TEST_AUDIENCE
    private_key, _ = generate_keypair()
    install_test_jwks(private_key)

    hs_token = jose_jwt.encode({"sub": "user1", "roles": ["bench_runner"]},
                               "test-secret", algorithm="HS256")
    with pytest.raises(Exception):
        verify_token(hs_token)

    other_key, _ = generate_keypair()
    foreign = mint_test_token(other_key, "user1", ["bench_runner"])
    with pytest.raises(Exception):
        verify_token(foreign)


def test_complete_run_publishes_bench_results(service):
    svc, publisher, _ = service
    t = svc.register_test("t1", "security")
    run = svc.start_run("target", [t.id])
    svc.submit_result(run.id, t.id, True, "ok")
    svc.complete_run(run.id)
    topics = [e.topic for e in publisher.drain()]
    assert "bench.results" in topics


def test_workflow_completed_handler_starts_run():
    from src.infra.kafka import KafkaEvent, build_asset_published_handler

    repo = SqlBenchRepository(connect_sqlite())
    svc = BenchService(repo)
    handler = build_asset_published_handler(svc, ["default-test"])
    event = KafkaEvent(
        topic="flow.workflow.completed",
        key="corr-1",
        payload={"target": "supplier-1", "suite": ["s1", "s2"]},
    )
    handler(event)
    runs = svc.list_runs()
    assert len(runs) == 1
    assert runs[0].target == "supplier-1"


def test_workflow_completed_handler_uses_envelope_payload():
    from src.infra.kafka import KafkaEvent, build_asset_published_handler

    repo = SqlBenchRepository(connect_sqlite())
    svc = BenchService(repo)
    handler = build_asset_published_handler(svc, [])
    event = KafkaEvent(
        topic="flow.workflow.completed",
        key="corr-2",
        payload={
            "event_id": "evt-1",
            "correlation_id": "corr-2",
            "payload": {"target": "supplier-2", "suite": ["s3"]},
        },
    )
    handler(event)
    runs = svc.list_runs()
    assert len(runs) == 1
    assert runs[0].target == "supplier-2"


def test_kafka_producer_fallback_buffer():
    from src.infra.kafka import KafkaEvent, KafkaProducer

    producer = KafkaProducer(bootstrap_servers="unreachable:9092")
    event = KafkaEvent(topic="bench.results", key="k", payload={"score": 1.0})
    result = producer.publish(event)
    assert result == "buffered"
    assert len(producer.buffered_events()) == 1
