"""SQL repository for the bench store (ADR-005, ADR-009).

SQLAlchemy backend: PostgreSQL in production (via the DATABASE_URL injected by
the platform), SQLite in dev/tests. The public API of SqlBenchRepository is
unchanged from the raw-sqlite3 version so services and the API layer are
untouched.
"""
import json
from datetime import datetime

from sqlalchemy import Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from ..core.domain.test_models import (
    Evidence,
    Report,
    RunStatus,
    Score,
    TestCase,
    TestResult,
    TestRun,
)


class Base(DeclarativeBase):
    pass


class TestCaseRow(Base):
    __tablename__ = "test_cases"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    version: Mapped[str] = mapped_column(String)


class TestRunRow(Base):
    __tablename__ = "test_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    target: Mapped[str] = mapped_column(String)
    suite: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String)
    started_at: Mapped[str] = mapped_column(String)
    completed_at: Mapped[str | None] = mapped_column(String, nullable=True)


class TestResultRow(Base):
    __tablename__ = "test_results"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String)
    test_case_id: Mapped[str] = mapped_column(String)
    passed: Mapped[int] = mapped_column(Integer)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScoreRow(Base):
    __tablename__ = "scores"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    target: Mapped[str] = mapped_column(String)
    dimension: Mapped[str] = mapped_column(String)
    value: Mapped[float] = mapped_column(Float)
    run_id: Mapped[str] = mapped_column(String)


class EvidenceRow(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String)
    artifact_url: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String)
    collected_at: Mapped[str] = mapped_column(String)


class ReportRow(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String)
    format: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String)


class SqlBenchRepository:
    """SQL-backed repository for test cases, runs, results, scores, evidence
    and reports. Accepts a SQLAlchemy DSN (PostgreSQL or SQLite)."""

    def __init__(self, dsn: str):
        # The image ships psycopg v3, not psycopg2: a bare `postgresql://` DSN
        # (SQLAlchemy's historical default) would crash on import. Pin the
        # explicit v3 driver for the default scheme.
        if dsn.startswith("postgresql://"):
            dsn = "postgresql+psycopg://" + dsn[len("postgresql://"):]
        kwargs = {}
        if dsn.startswith("sqlite") and ":memory:" in dsn:
            # Keep a single shared in-memory database across sessions and
            # threads (dev/tests), mirroring the old check_same_thread=False
            # sqlite3 connection handed around directly.
            kwargs["poolclass"] = StaticPool
            kwargs["connect_args"] = {"check_same_thread": False}
        self.engine = create_engine(dsn, **kwargs)
        self._sessionmaker = sessionmaker(bind=self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self._sessionmaker()

    # -- test cases -----------------------------------------------------------

    def save_test(self, test: TestCase) -> None:
        with self.session() as s:
            row = s.get(TestCaseRow, test.id)
            if row is None:
                s.add(TestCaseRow(id=test.id, name=test.name,
                                  category=test.category, version=test.version))
            else:
                row.name = test.name
                row.category = test.category
                row.version = test.version
            s.commit()

    def get_test(self, test_id: str) -> TestCase | None:
        with self.session() as s:
            row = s.get(TestCaseRow, test_id)
            return self._to_test(row) if row else None

    def list_tests(self) -> list:
        with self.session() as s:
            rows = s.query(TestCaseRow).all()
            return [self._to_test(r) for r in rows]

    # -- runs -----------------------------------------------------------------

    def save_run(self, run: TestRun) -> None:
        with self.session() as s:
            row = s.get(TestRunRow, run.id)
            if row is None:
                s.add(TestRunRow(
                    id=run.id, target=run.target,
                    suite=json.dumps(run.suite), status=run.status.value,
                    started_at=run.started_at.isoformat(),
                    completed_at=(run.completed_at.isoformat()
                                  if run.completed_at else None)))
            else:
                row.status = run.status.value
                row.completed_at = (run.completed_at.isoformat()
                                    if run.completed_at else None)
            s.commit()

    def get_run(self, run_id: str) -> TestRun | None:
        with self.session() as s:
            row = s.get(TestRunRow, run_id)
            return self._to_run(row) if row else None

    def list_runs(self) -> list:
        with self.session() as s:
            rows = (s.query(TestRunRow)
                    .order_by(TestRunRow.started_at.desc()).all())
            return [self._to_run(r) for r in rows]

    # -- results --------------------------------------------------------------

    def save_result(self, result: TestResult) -> None:
        with self.session() as s:
            s.add(TestResultRow(
                id=result.id, run_id=result.run_id,
                test_case_id=result.test_case_id,
                passed=int(result.passed), details=result.details))
            s.commit()

    def get_results(self, run_id: str) -> list:
        with self.session() as s:
            rows = s.query(TestResultRow).filter_by(run_id=run_id).all()
            return [self._to_result(r) for r in rows]

    # -- scores ---------------------------------------------------------------

    def save_score(self, score: Score) -> None:
        with self.session() as s:
            s.add(ScoreRow(id=score.id, target=score.target,
                           dimension=score.dimension, value=score.value,
                           run_id=score.run_id))
            s.commit()

    def list_scores(self, target: str | None = None) -> list:
        with self.session() as s:
            q = s.query(ScoreRow)
            if target:
                q = q.filter_by(target=target)
            return [self._to_score(r) for r in q.all()]

    # -- evidence -------------------------------------------------------------

    def save_evidence(self, evidence: Evidence) -> None:
        with self.session() as s:
            s.add(EvidenceRow(
                id=evidence.id, run_id=evidence.run_id,
                artifact_url=evidence.artifact_url, sha256=evidence.sha256,
                collected_at=evidence.collected_at.isoformat()))
            s.commit()

    def get_evidence(self, run_id: str) -> list:
        with self.session() as s:
            rows = s.query(EvidenceRow).filter_by(run_id=run_id).all()
            return [self._to_evidence(r) for r in rows]

    # -- reports --------------------------------------------------------------

    def save_report(self, report: Report) -> None:
        with self.session() as s:
            s.add(ReportRow(
                id=report.id, run_id=report.run_id, format=report.format,
                content=report.content, created_at=report.created_at.isoformat()))
            s.commit()

    def get_report(self, run_id: str) -> Report | None:
        with self.session() as s:
            row = (s.query(ReportRow)
                   .filter_by(run_id=run_id)
                   .order_by(ReportRow.created_at.desc())
                   .first())
            return self._to_report(row) if row else None

    # -- internals ------------------------------------------------------------

    def _to_test(self, row: TestCaseRow) -> TestCase:
        return TestCase(id=row.id, name=row.name,
                        category=row.category, version=row.version)

    def _to_run(self, row: TestRunRow) -> TestRun:
        return TestRun(
            id=row.id, target=row.target,
            suite=json.loads(row.suite),
            status=RunStatus(row.status),
            started_at=_dt(row.started_at),
            completed_at=_dt(row.completed_at))

    def _to_result(self, row: TestResultRow) -> TestResult:
        return TestResult(id=row.id, run_id=row.run_id,
                          test_case_id=row.test_case_id,
                          passed=bool(row.passed), details=row.details)

    def _to_score(self, row: ScoreRow) -> Score:
        return Score(id=row.id, target=row.target,
                     dimension=row.dimension, value=row.value,
                     run_id=row.run_id)

    def _to_evidence(self, row: EvidenceRow) -> Evidence:
        return Evidence(
            id=row.id, run_id=row.run_id,
            artifact_url=row.artifact_url, sha256=row.sha256,
            collected_at=_dt(row.collected_at))

    def _to_report(self, row: ReportRow) -> Report:
        return Report(
            id=row.id, run_id=row.run_id,
            format=row.format, content=row.content,
            created_at=_dt(row.created_at))


def connect_sqlite(path: str = ":memory:") -> str:
    """Return a SQLAlchemy SQLite DSN for dev/tests (in-memory by default)."""
    if path == ":memory:":
        return "sqlite+pysqlite:///:memory:"
    return f"sqlite+pysqlite:///{path}"


def _dt(value):
    return datetime.fromisoformat(value) if value else None
