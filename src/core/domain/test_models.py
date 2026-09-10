"""Test domain model for arca-bench (ADR-001, ADR-005).

Aggregates and value objects:
- TestCase: an immutable catalog entry (name, category, version).
- TestRun: an aggregate root that runs a suite of test-case names against a target.
- TestResult: a value object recording the outcome of one test case in a run.
- Score: a value object produced from a set of results.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def _now():
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class TestCase:
    name: str
    category: str
    version: str = "1.0.0"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        if not self.name or not self.category:
            raise ValueError("name and category are required")

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name,
                "category": self.category, "version": self.version}


class RunStatus(str, Enum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TestRun:
    target: str
    suite: list
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: RunStatus = RunStatus.STARTED
    started_at: datetime = field(default_factory=_now)
    completed_at: datetime | None = None

    def __post_init__(self):
        if not self.target or not self.suite:
            raise ValueError("target and suite are required")

    def complete(self) -> None:
        if self.status is not RunStatus.STARTED:
            raise ValueError(f"run {self.id} is {self.status.value}")
        self.status = RunStatus.COMPLETED
        self.completed_at = _now()

    def fail(self, reason: str) -> None:
        if self.status is not RunStatus.STARTED:
            raise ValueError(f"run {self.id} is {self.status.value}")
        self.status = RunStatus.FAILED
        self.completed_at = _now()


@dataclass(frozen=True)
class TestResult:
    run_id: str
    test_case_id: str
    passed: bool
    details: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return {"id": self.id, "run_id": self.run_id,
                "test_case_id": self.test_case_id, "passed": self.passed,
                "details": self.details}


@dataclass(frozen=True)
class Score:
    target: str
    dimension: str
    value: float
    run_id: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        if not 0.0 <= self.value <= 1.0:
            raise ValueError("score value must be in [0, 1]")

    def to_dict(self) -> dict:
        return {"id": self.id, "target": self.target,
                "dimension": self.dimension, "value": self.value,
                "run_id": self.run_id}
