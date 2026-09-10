"""Bench application service (ADR-001, ADR-003, ADR-004).

- TestRegistry: catalog of reusable test cases.
- TestRunner: executes a suite against a target and records results.
- ScoreEngine: computes Arca scores from results per dimension.
"""
from ..domain.test_models import RunStatus, Score, TestCase, TestResult, TestRun
from ..events.bench_events import (
    OutboxPublisher,
    run_completed,
    run_started,
    score_published,
)


class BenchService:
    def __init__(self, repository, publisher: OutboxPublisher | None = None):
        self._repo = repository
        self._publisher = publisher or OutboxPublisher()

    # -- catalog --------------------------------------------------------------

    def register_test(self, name: str, category: str,
                      version: str = "1.0.0") -> TestCase:
        test = TestCase(name=name, category=category, version=version)
        self._repo.save_test(test)
        return test

    def list_tests(self) -> list:
        return self._repo.list_tests()

    # -- execution ------------------------------------------------------------

    def start_run(self, target: str, suite: list) -> TestRun:
        if not target or not suite:
            raise ValueError("target and suite are required")
        run = TestRun(target=target, suite=suite)
        self._repo.save_run(run)
        self._publisher.publish(run_started(run))
        return run

    def submit_result(self, run_id: str, test_case_id: str,
                      passed: bool, details: str = "") -> TestResult:
        run = self._repo.get_run(run_id)
        if run is None:
            raise LookupError(f"run {run_id} not found")
        if run.status is not RunStatus.STARTED:
            raise ValueError("cannot add results to a completed or failed run")
        result = TestResult(run_id=run_id, test_case_id=test_case_id,
                            passed=passed, details=details)
        self._repo.save_result(result)
        return result

    def complete_run(self, run_id: str) -> dict:
        run = self._repo.get_run(run_id)
        if run is None:
            raise LookupError(f"run {run_id} not found")
        results = self._repo.get_results(run_id)
        run.complete()
        self._repo.save_run(run)
        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        self._publisher.publish(run_completed(run, passed, failed))
        scores = self._compute_scores(run, results)
        for score in scores:
            self._repo.save_score(score)
            self._publisher.publish(score_published(score))
        return {"run_id": run.id, "status": run.status.value,
                "passed": passed, "failed": failed,
                "scores": [s.to_dict() for s in scores]}

    def fail_run(self, run_id: str, reason: str) -> TestRun:
        run = self._repo.get_run(run_id)
        if run is None:
            raise LookupError(f"run {run_id} not found")
        run.fail(reason)
        self._repo.save_run(run)
        self._publisher.publish(run_completed(run, 0, 0))
        return run

    # -- reads ----------------------------------------------------------------

    def get_run(self, run_id: str):
        return self._repo.get_run(run_id)

    def get_results(self, run_id: str) -> list:
        return self._repo.get_results(run_id)

    def get_scores(self, target: str | None = None) -> list:
        return self._repo.list_scores(target=target)

    # -- internals ------------------------------------------------------------

    def _compute_scores(self, run: TestRun, results: list) -> list:
        if not results:
            return []
        # Map category -> pass ratio.
        by_category: dict = {}
        for result in results:
            test = self._repo.get_test(result.test_case_id)
            category = test.category if test else "unknown"
            by_category.setdefault(category, []).append(result.passed)
        return [
            Score(target=run.target, dimension=category,
                  value=sum(outcomes) / len(outcomes), run_id=run.id)
            for category, outcomes in by_category.items()
        ]
