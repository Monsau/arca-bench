"""REST handlers. Endpoints follow ADR-002; schemas follow contracts/rest/openapi.yaml."""
from fastapi import APIRouter, Depends, HTTPException, Request

from ..config import settings
from ..core.security.jwt import require_role
from ..policies.abac import can_access_target, can_run_in_environment

router = APIRouter(prefix="/api/v1", tags=["arca-bench"])


def _service(request: Request):
    return request.app.state.bench_service


def _replay(request: Request):
    return request.app.state.decision_replay


def _soc(request: Request):
    return request.app.state.soc


@router.get("/bench/health")
def api_health():
    return {"service": settings.app_name, "status": "ok"}


@router.get("/tests")
def list_tests(request: Request, user=Depends(require_role("bench_admin", "bench_runner", "bench_reader"))):
    return {"tests": [t.to_dict() for t in _service(request).list_tests()]}


@router.post("/tests", status_code=201)
def register_test(body: dict, request: Request,
                  user=Depends(require_role("bench_admin", "bench_runner"))):
    name = (body or {}).get("name")
    category = (body or {}).get("category")
    version = (body or {}).get("version", "1.0.0")
    if not name or not category:
        raise HTTPException(status_code=422, detail="name and category required")
    test = _service(request).register_test(name, category, version)
    return test.to_dict()


@router.get("/runs")
def list_runs(request: Request):
    runs = _service(request).list_runs()
    return {"runs": [_run_dict(r) for r in runs]}


@router.post("/runs", status_code=202)
def start_run(body: dict, request: Request,
              user=Depends(require_role("bench_admin", "bench_runner"))):
    target = (body or {}).get("target")
    suite = (body or {}).get("suite")
    environment = (body or {}).get("environment")
    if not target or not suite:
        raise HTTPException(status_code=422, detail="target and suite required")
    # ABAC (ADR-009): the JWT may restrict which targets and environments
    # this principal may run against; denial is a 403, not a silent no-op.
    if not can_access_target(user, target):
        raise HTTPException(status_code=403, detail="target not allowed for this principal")
    if environment and not can_run_in_environment(user, environment):
        raise HTTPException(status_code=403,
                            detail="environment not allowed for this principal")
    run = _service(request).start_run(target, suite)
    return {"run_id": run.id, "status": run.status.value,
            "correlation_id": run.id}


@router.get("/runs/{run_id}")
def get_run(run_id: str, request: Request, user=Depends(require_role("bench_admin", "bench_runner", "bench_reader"))):
    run = _service(request).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return _run_dict(run)


@router.post("/runs/{run_id}/results", status_code=201)
def submit_result(run_id: str, body: dict, request: Request,
                  user=Depends(require_role("bench_admin", "bench_runner"))):
    body = body or {}
    test_case_id = body.get("test_case_id")
    passed = body.get("passed")
    if test_case_id is None or passed is None:
        raise HTTPException(status_code=422,
                            detail="test_case_id and passed required")
    try:
        result = _service(request).submit_result(
            run_id, test_case_id, bool(passed), body.get("details", ""))
    except LookupError:
        raise HTTPException(status_code=404, detail="run not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return result.to_dict()


@router.post("/runs/{run_id}/complete")
def complete_run(run_id: str, request: Request,
                 user=Depends(require_role("bench_admin", "bench_runner"))):
    try:
        return _service(request).complete_run(run_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="run not found")


@router.post("/runs/{run_id}/evidence", status_code=201)
def collect_evidence(run_id: str, body: dict, request: Request,
                     user=Depends(require_role("bench_admin", "bench_runner"))):
    body = body or {}
    url = body.get("artifact_url")
    content = body.get("content", "").encode("utf-8") if "content" in body else None
    if not url:
        raise HTTPException(status_code=422, detail="artifact_url required")
    try:
        evidence = _service(request).collect_evidence(run_id, url, content)
    except LookupError:
        raise HTTPException(status_code=404, detail="run not found")
    return evidence.to_dict()


@router.get("/runs/{run_id}/evidence")
def list_evidence(run_id: str, request: Request, user=Depends(require_role("bench_admin", "bench_runner", "bench_reader"))):
    return {"evidence": [e.to_dict() for e in _service(request).list_evidence(run_id)]}


@router.get("/runs/{run_id}/report")
def get_report(run_id: str, request: Request, format: str = "json",
               user=Depends(require_role("bench_admin", "bench_runner", "bench_reader"))):
    try:
        report = _service(request).generate_report(run_id, format)
    except LookupError:
        raise HTTPException(status_code=404, detail="run not found")
    return report.to_dict()


@router.get("/scores")
def list_scores(target: str | None = None, request: Request = None,
                user=Depends(require_role("bench_admin", "bench_runner", "bench_reader"))):
    scores = _service(request).get_scores(target=target)
    return {"scores": [s.to_dict() for s in scores]}


@router.get("/scorecards/{run_id}")
def get_scorecard(run_id: str, request: Request,
                  user=Depends(require_role("bench_admin", "bench_runner", "bench_reader"))):
    try:
        scorecard = _service(request).get_scorecard(run_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="run not found")
    return scorecard.to_dict()


# -- external decision replay (reward-loop breaker) --------------------------
# The bench re-computes the sealed outcome from the package inputs and checks
# the quorum from the package contents only — never from module-emitted
# events. Rules are registered bench-side (see src/main.py lifespan).

@router.get("/decision-replay/rules")
def list_replay_rules(request: Request,
                      user=Depends(require_role("bench_admin", "bench_runner", "bench_reader"))):
    return {"rules": _replay(request).list_rules()}


@router.post("/decision-replay/evaluate")
def evaluate_decision(body: dict, request: Request,
                      user=Depends(require_role("bench_admin", "bench_runner"))):
    from datetime import datetime

    from ..core.services.decision_replay import (
        Approval,
        RuleNotRegistered,
        SealedDecisionPackage,
    )
    body = body or {}
    try:
        approvals = tuple(
            Approval(voter_id=a["voter_id"], role=a["role"],
                     approved_at=datetime.fromisoformat(a["approved_at"]),
                     approved=bool(a.get("approved", True)))
            for a in body["approvals"])
        sealed_at = (datetime.fromisoformat(body["sealed_at"])
                     if body.get("sealed_at") else None)
        package = SealedDecisionPackage(
            decision_id=body["decision_id"], rule_id=body["rule_id"],
            inputs=body["inputs"], sealed_outcome=body["sealed_outcome"],
            approvals=approvals, quorum_required=int(body["quorum_required"]),
            required_roles=frozenset(body.get("required_roles", [])),
            sealed_by=body.get("sealed_by", ""), sealed_at=sealed_at,
            evidence_hash=body.get("evidence_hash"))
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid package: {exc}")
    try:
        verdict = _replay(request).evaluate(package)
    except RuleNotRegistered as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return verdict.to_dict()


def _run_dict(run) -> dict:
    return {"run_id": run.id, "target": run.target, "suite": run.suite,
            "status": run.status.value,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None}
