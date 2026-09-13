"""Scoring engine (ADR-001, ADR-009)."""
from ..domain.test_models import Score, Scorecard


class ScoringEngine:
    def __init__(self, repository):
        self._repo = repository

    def compute_scores(self, run, results: list) -> list:
        if not results:
            return []
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

    def build_scorecard(self, run, scores: list) -> Scorecard:
        dimensions = {s.dimension: s.value for s in scores}
        overall = sum(dimensions.values()) / len(dimensions) if dimensions else 0.0
        return Scorecard(target=run.target, dimensions=dimensions,
                         overall=overall, run_id=run.id)
