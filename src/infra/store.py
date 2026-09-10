"""SQL repository for the bench store (ADR-005).

PostgreSQL in production; SQLite is accepted for dev/tests.
"""
import json
import sqlite3
from datetime import datetime

from ..core.domain.test_models import RunStatus, Score, TestCase, TestResult, TestRun

_SCHEMA = """
CREATE TABLE IF NOT EXISTS test_cases (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS test_runs (
    id TEXT PRIMARY KEY,
    target TEXT NOT NULL,
    suite TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS test_results (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    test_case_id TEXT NOT NULL,
    passed INTEGER NOT NULL,
    details TEXT
);
CREATE TABLE IF NOT EXISTS scores (
    id TEXT PRIMARY KEY,
    target TEXT NOT NULL,
    dimension TEXT NOT NULL,
    value REAL NOT NULL,
    run_id TEXT NOT NULL
);
"""


class SqlBenchRepository:
    def __init__(self, connection: sqlite3.Connection):
        self._conn = connection
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- test cases -----------------------------------------------------------

    def save_test(self, test: TestCase) -> None:
        self._conn.execute(
            "INSERT INTO test_cases (id, name, category, version)"
            " VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET"
            " name=excluded.name, category=excluded.category,"
            " version=excluded.version",
            (test.id, test.name, test.category, test.version))
        self._conn.commit()

    def get_test(self, test_id: str) -> TestCase | None:
        row = self._conn.execute(
            "SELECT * FROM test_cases WHERE id = ?", (test_id,)).fetchone()
        return self._to_test(row) if row else None

    def list_tests(self) -> list:
        rows = self._conn.execute("SELECT * FROM test_cases").fetchall()
        return [self._to_test(r) for r in rows]

    # -- runs -----------------------------------------------------------------

    def save_run(self, run: TestRun) -> None:
        self._conn.execute(
            "INSERT INTO test_runs (id, target, suite, status, started_at,"
            " completed_at) VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET"
            " status=excluded.status, completed_at=excluded.completed_at",
            (run.id, run.target, json.dumps(run.suite), run.status.value,
             run.started_at.isoformat(),
             run.completed_at.isoformat() if run.completed_at else None))
        self._conn.commit()

    def get_run(self, run_id: str) -> TestRun | None:
        row = self._conn.execute(
            "SELECT * FROM test_runs WHERE id = ?", (run_id,)).fetchone()
        return self._to_run(row) if row else None

    # -- results --------------------------------------------------------------

    def save_result(self, result: TestResult) -> None:
        self._conn.execute(
            "INSERT INTO test_results (id, run_id, test_case_id, passed, details)"
            " VALUES (?,?,?,?,?)",
            (result.id, result.run_id, result.test_case_id,
             int(result.passed), result.details))
        self._conn.commit()

    def get_results(self, run_id: str) -> list:
        rows = self._conn.execute(
            "SELECT * FROM test_results WHERE run_id = ?", (run_id,)).fetchall()
        return [self._to_result(r) for r in rows]

    # -- scores ---------------------------------------------------------------

    def save_score(self, score: Score) -> None:
        self._conn.execute(
            "INSERT INTO scores (id, target, dimension, value, run_id)"
            " VALUES (?,?,?,?,?)",
            (score.id, score.target, score.dimension, score.value, score.run_id))
        self._conn.commit()

    def list_scores(self, target: str | None = None) -> list:
        if target:
            rows = self._conn.execute(
                "SELECT * FROM scores WHERE target = ?", (target,)).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM scores").fetchall()
        return [self._to_score(r) for r in rows]

    # -- internals ------------------------------------------------------------

    def _to_test(self, row) -> TestCase:
        return TestCase(id=row["id"], name=row["name"],
                        category=row["category"], version=row["version"])

    def _to_run(self, row) -> TestRun:
        return TestRun(
            id=row["id"], target=row["target"],
            suite=json.loads(row["suite"]),
            status=RunStatus(row["status"]),
            started_at=_dt(row["started_at"]),
            completed_at=_dt(row["completed_at"]))

    def _to_result(self, row) -> TestResult:
        return TestResult(id=row["id"], run_id=row["run_id"],
                          test_case_id=row["test_case_id"],
                          passed=bool(row["passed"]), details=row["details"])

    def _to_score(self, row) -> Score:
        return Score(id=row["id"], target=row["target"],
                     dimension=row["dimension"], value=row["value"],
                     run_id=row["run_id"])


def connect_sqlite(path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _dt(value):
    return datetime.fromisoformat(value) if value else None
