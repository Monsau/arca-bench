"""Test runner engine (ADR-001, ADR-009)."""
from ..domain.test_models import RunStatus, TestResult, TestRun


class TestRunnerEngine:
    def __init__(self, repository):
        self._repo = repository

    def start_run(self, target: str, suite: list) -> TestRun:
        if not target or suite is None:
            raise ValueError("target and suite are required")
        run = TestRun(target=target, suite=suite)
        self._repo.save_run(run)
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

    def complete_run(self, run_id: str) -> tuple[TestRun, list]:
        run = self._repo.get_run(run_id)
        if run is None:
            raise LookupError(f"run {run_id} not found")
        results = self._repo.get_results(run_id)
        run.complete()
        self._repo.save_run(run)
        return run, results

    def fail_run(self, run_id: str, reason: str) -> TestRun:
        run = self._repo.get_run(run_id)
        if run is None:
            raise LookupError(f"run {run_id} not found")
        run.fail(reason)
        self._repo.save_run(run)
        return run

    def get_run(self, run_id: str) -> TestRun | None:
        return self._repo.get_run(run_id)

    def list_runs(self) -> list:
        return self._repo.list_runs()

    def get_results(self, run_id: str) -> list:
        return self._repo.get_results(run_id)
