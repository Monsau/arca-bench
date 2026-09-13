"""Test registry service (ADR-001, ADR-009)."""
from ..domain.test_models import TestCase


class TestRegistry:
    def __init__(self, repository):
        self._repo = repository

    def register_test(self, name: str, category: str,
                      version: str = "1.0.0") -> TestCase:
        test = TestCase(name=name, category=category, version=version)
        self._repo.save_test(test)
        return test

    def list_tests(self) -> list:
        return self._repo.list_tests()

    def get_test(self, test_id: str) -> TestCase | None:
        return self._repo.get_test(test_id)
