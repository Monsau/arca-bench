"""GraphQL schema and resolvers. Types follow contracts/graphql/schema.graphql (ADR-002, ADR-009)."""
import json
from datetime import datetime
from typing import List, Optional

import strawberry
from fastapi import Request
from strawberry.fastapi import GraphQLRouter
from strawberry.types import Info

from ..core.security.jwt import verify_token


@strawberry.type
class TestCase:
    id: str
    name: str
    category: str
    version: str


@strawberry.type
class TestRun:
    id: str
    target: str
    suite: List[str]
    status: str
    started_at: str
    completed_at: Optional[str]


@strawberry.type
class TestResult:
    id: str
    run_id: str
    test_case_id: str
    passed: bool
    details: str


@strawberry.type
class Score:
    id: str
    target: str
    dimension: str
    value: float
    run_id: str


@strawberry.type
class Scorecard:
    target: str
    dimensions: str
    overall: float
    run_id: str
    generated_at: str


@strawberry.type
class Report:
    id: str
    run_id: str
    format: str
    content: str
    created_at: str


@strawberry.type
class Query:
    @strawberry.field
    def tests(self, info: Info) -> List[TestCase]:
        svc = info.context["service"]
        return [TestCase(**t.to_dict()) for t in svc.list_tests()]

    @strawberry.field
    def runs(self, info: Info) -> List[TestRun]:
        svc = info.context["service"]
        return [_to_run(r) for r in svc.list_runs()]

    @strawberry.field
    def run(self, info: Info, id: str) -> Optional[TestRun]:
        svc = info.context["service"]
        r = svc.get_run(id)
        return _to_run(r) if r else None

    @strawberry.field
    def scores(self, info: Info, target: str) -> List[Score]:
        svc = info.context["service"]
        return [Score(**s.to_dict()) for s in svc.get_scores(target=target)]

    @strawberry.field
    def scorecard(self, info: Info, run_id: str) -> Scorecard:
        svc = info.context["service"]
        sc = svc.get_scorecard(run_id)
        # dimensions is exposed as a JSON document (String in SDL) so the
        # contract stays schema-stable without a nested dynamic type.
        return Scorecard(
            target=sc.target,
            dimensions=json.dumps(sc.dimensions),
            overall=sc.overall,
            run_id=sc.run_id,
            generated_at=sc.generated_at.isoformat())

    @strawberry.field
    def report(self, info: Info, run_id: str, format: str = "json") -> Report:
        svc = info.context["service"]
        r = svc.generate_report(run_id, format)
        return Report(**r.to_dict())


@strawberry.type
class Mutation:
    @strawberry.mutation
    def register_test(self, info: Info, name: str,
                      category: str, version: str = "1.0.0") -> TestCase:
        _require_role(info, "bench_admin", "bench_runner")
        test = info.context["service"].register_test(name, category, version)
        return TestCase(**test.to_dict())

    @strawberry.mutation
    def start_run(self, info: Info, target: str, suite: List[str]) -> TestRun:
        _require_role(info, "bench_admin", "bench_runner")
        run = info.context["service"].start_run(target, suite)
        return _to_run(run)

    @strawberry.mutation
    def submit_result(self, info: Info, run_id: str, test_case_id: str,
                      passed: bool, details: str = "") -> TestResult:
        _require_role(info, "bench_admin", "bench_runner")
        result = info.context["service"].submit_result(
            run_id, test_case_id, passed, details)
        return TestResult(**result.to_dict())

    @strawberry.mutation
    def complete_run(self, info: Info, run_id: str) -> str:
        _require_role(info, "bench_admin", "bench_runner")
        summary = info.context["service"].complete_run(run_id)
        return summary["run_id"]


def _to_run(run) -> TestRun:
    return TestRun(
        id=run.id, target=run.target, suite=run.suite,
        status=run.status.value,
        started_at=run.started_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None)


def _require_role(info: Info, *roles):
    user = info.context.get("user") or {}
    user_roles = set(user.get("roles", []))
    if not any(r in user_roles for r in roles):
        raise Exception("Insufficient role")


schema = strawberry.Schema(query=Query, mutation=Mutation)


def _get_context(request: Request):
    service = request.app.state.bench_service
    token = request.headers.get("authorization", "")
    user = None
    if token.lower().startswith("bearer "):
        try:
            user = verify_token(token[7:])
        except Exception:
            user = None
    else:
        user = verify_token("")
    return {"request": request, "service": service, "user": user}


graphql_router = GraphQLRouter(schema, context_getter=_get_context)
