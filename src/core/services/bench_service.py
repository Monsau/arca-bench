"""Bench application service facade (ADR-001, ADR-003, ADR-004, ADR-009).

Orchestrates TestRegistry, TestRunnerEngine, ScoringEngine, EvidenceCollector
and ReportGenerator. Publishes domain events through an OutboxPublisher and
routes every mutation through the embedded SOC for audit and telemetry.
"""
from ...infra.soc import EmbeddedSOC, audit_operation
from ..events.bench_events import (
    OutboxPublisher,
    bench_results,
    evidence_collected,
    report_generated,
    run_completed,
    run_started,
    score_published,
)
from .evidence import EvidenceCollector
from .registry import TestRegistry
from .reporting import ReportGenerator
from .runner import TestRunnerEngine
from .scoring import ScoringEngine


class BenchService:
    def __init__(self, repository,
                 publisher=None,
                 soc: EmbeddedSOC | None = None):
        self._repo = repository
        self._publisher = publisher or OutboxPublisher()
        self._soc = soc or EmbeddedSOC()
        self.registry = TestRegistry(repository)
        self.runner = TestRunnerEngine(repository)
        self.scoring = ScoringEngine(repository)
        self.evidence = EvidenceCollector(repository)
        self.reports = ReportGenerator(repository)

    def _audit(self, operation: str, correlation_id: str,
               entity_type: str = None, entity_id: str = None):
        return audit_operation(self._soc, operation, correlation_id,
                               entity_type, entity_id)

    def _soc_event(self, event_type: str, payload: dict,
                   correlation_id: str):
        self._soc.collector.collect_event(event_type, payload,
                                          correlation_id)

    # -- catalog --------------------------------------------------------------

    def register_test(self, name: str, category: str,
                      version: str = "1.0.0"):
        with self._audit("register_test", correlation_id=f"test:{name}",
                         entity_type="test_case", entity_id=name):
            test = self.registry.register_test(name, category, version)
            self._soc_event("test_registered", test.to_dict(), test.id)
            return test

    def list_tests(self) -> list:
        return self.registry.list_tests()

    # -- execution ------------------------------------------------------------

    def start_run(self, target: str, suite: list):
        with self._audit("start_run", correlation_id=f"run:{target}",
                         entity_type="target", entity_id=target):
            run = self.runner.start_run(target, suite)
            self._publisher.publish(run_started(run))
            self._soc_event("run_started", {"run_id": run.id,
                                            "target": run.target}, run.id)
            return run

    def submit_result(self, run_id: str, test_case_id: str,
                      passed: bool, details: str = ""):
        with self._audit("submit_result", correlation_id=run_id,
                         entity_type="run", entity_id=run_id):
            result = self.runner.submit_result(run_id, test_case_id, passed,
                                               details)
            self._soc_event("result_submitted", result.to_dict(), run_id)
            return result

    def complete_run(self, run_id: str) -> dict:
        with self._audit("complete_run", correlation_id=run_id,
                         entity_type="run", entity_id=run_id):
            run, results = self.runner.complete_run(run_id)
            passed = sum(1 for r in results if r.passed)
            failed = len(results) - passed
            self._publisher.publish(run_completed(run, passed, failed))
            self._soc_event("run_completed", {
                "run_id": run.id, "status": run.status.value,
                "passed": passed, "failed": failed}, run.id)
            scores = self.scoring.compute_scores(run, results)
            for score in scores:
                self._repo.save_score(score)
                self._publisher.publish(score_published(score))
            scorecard = self.scoring.build_scorecard(run, scores)
            self._publisher.publish(bench_results(run, scorecard, failed=failed))
            anomalies = (self._soc.analyzer.detect_anomaly("run_failure_rate", 0.1)
                         if self._soc else [])
            if anomalies:
                self._soc.responder.escalate(run.id, "high")
            return {"run_id": run.id, "status": run.status.value,
                    "passed": passed, "failed": failed,
                    "scores": [s.to_dict() for s in scores],
                    "scorecard": scorecard.to_dict()}

    def fail_run(self, run_id: str, reason: str):
        with self._audit("fail_run", correlation_id=run_id,
                         entity_type="run", entity_id=run_id):
            run = self.runner.fail_run(run_id, reason)
            self._publisher.publish(run_completed(run, 0, 0))
            self._soc_event("run_failed", {"run_id": run.id,
                                           "reason": reason}, run.id)
            return run

    # -- reads ----------------------------------------------------------------

    def get_run(self, run_id: str):
        return self.runner.get_run(run_id)

    def list_runs(self) -> list:
        return self.runner.list_runs()

    def get_results(self, run_id: str) -> list:
        return self.runner.get_results(run_id)

    def get_scores(self, target: str | None = None) -> list:
        return self._repo.list_scores(target=target)

    def get_scorecard(self, run_id: str):
        run = self.runner.get_run(run_id)
        if run is None:
            raise LookupError(f"run {run_id} not found")
        scores = self._repo.list_scores(target=run.target)
        run_scores = [s for s in scores if s.run_id == run_id]
        return self.scoring.build_scorecard(run, run_scores)

    # -- evidence -------------------------------------------------------------

    def collect_evidence(self, run_id: str, artifact_url: str,
                         content: bytes | None = None):
        with self._audit("collect_evidence", correlation_id=run_id,
                         entity_type="run", entity_id=run_id):
            evidence = self.evidence.collect_evidence(run_id, artifact_url,
                                                      content)
            self._publisher.publish(evidence_collected(evidence))
            self._soc_event("evidence_collected", evidence.to_dict(), run_id)
            return evidence

    def list_evidence(self, run_id: str) -> list:
        return self.evidence.list_evidence(run_id)

    # -- reports --------------------------------------------------------------

    def generate_report(self, run_id: str, format: str = "json"):
        with self._audit("generate_report", correlation_id=run_id,
                         entity_type="run", entity_id=run_id):
            run = self.runner.get_run(run_id)
            if run is None:
                raise LookupError(f"run {run_id} not found")
            results = self.runner.get_results(run_id)
            scores = [s for s in self._repo.list_scores(target=run.target)
                      if s.run_id == run_id]
            scorecard = self.scoring.build_scorecard(run, scores)
            report = self.reports.generate_report(run, results, scorecard,
                                                  format)
            self._publisher.publish(report_generated(report))
            self._soc_event("report_generated", report.to_dict(), run_id)
            return report
