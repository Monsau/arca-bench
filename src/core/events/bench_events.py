"""Bench domain events (ADR-003, ADR-009)."""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

TOPIC_RUN_STARTED = "bench.run.started"
TOPIC_RUN_COMPLETED = "bench.run.completed"
TOPIC_SCORE_PUBLISHED = "bench.score.published"
TOPIC_EVIDENCE_COLLECTED = "bench.evidence.collected"
TOPIC_REPORT_GENERATED = "bench.report.generated"
TOPIC_BENCH_RESULTS = "bench.results"


@dataclass(frozen=True)
class DomainEvent:
    topic: str
    key: str
    payload: dict
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def run_started(run) -> DomainEvent:
    return DomainEvent(
        topic=TOPIC_RUN_STARTED,
        key=run.id,
        payload={"run_id": run.id, "target": run.target,
                 "started_at": run.started_at.isoformat()},
    )


def run_completed(run, passed: int, failed: int) -> DomainEvent:
    return DomainEvent(
        topic=TOPIC_RUN_COMPLETED,
        key=run.id,
        payload={"run_id": run.id, "status": run.status.value,
                 "passed_count": passed, "failed_count": failed,
                 "completed_at": run.completed_at.isoformat()},
    )


def score_published(score) -> DomainEvent:
    return DomainEvent(
        topic=TOPIC_SCORE_PUBLISHED,
        key=score.run_id,
        payload={"score_id": score.id, "run_id": score.run_id,
                 "target": score.target, "dimension": score.dimension,
                 "value": score.value},
    )


def evidence_collected(evidence) -> DomainEvent:
    return DomainEvent(
        topic=TOPIC_EVIDENCE_COLLECTED,
        key=evidence.run_id,
        payload={"evidence_id": evidence.id, "run_id": evidence.run_id,
                 "artifact_url": evidence.artifact_url,
                 "sha256": evidence.sha256,
                 "collected_at": evidence.collected_at.isoformat()},
    )


def report_generated(report) -> DomainEvent:
    return DomainEvent(
        topic=TOPIC_REPORT_GENERATED,
        key=report.run_id,
        payload={"report_id": report.id, "run_id": report.run_id,
                 "format": report.format,
                 "created_at": report.created_at.isoformat()},
    )


def bench_results(run, scorecard, failed: int = 0,
                  report_id: str | None = None) -> DomainEvent:
    evidence = [{"source": "bench",
                 "ref_id": report_id or run.id,
                 "description": "bench run completed"}]
    return DomainEvent(
        topic=TOPIC_BENCH_RESULTS,
        key=run.id,
        payload={
            "event_id": f"evt-{uuid.uuid4().hex[:12]}",
            "correlation_id": run.id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "actor": None,
            "payload": {
                "bench_id": run.id,
                "target": run.target,
                "dimension": "supplier-risk",
                "passed": failed == 0,
                "score": scorecard.overall,
                "evidence": evidence,
            },
        },
    )


class OutboxPublisher:
    def __init__(self):
        self._events: list = []

    def publish(self, event: DomainEvent) -> None:
        self._events.append(event)

    def drain(self) -> list:
        events, self._events = self._events, []
        return events


class KafkaDomainEventPublisher:
    def __init__(self, producer):
        self._producer = producer

    def publish(self, event: DomainEvent) -> None:
        from ...infra.kafka import KafkaEvent as InfraKafkaEvent
        self._producer.publish(
            InfraKafkaEvent(
                topic=event.topic,
                key=event.key,
                payload=event.payload,
            )
        )
