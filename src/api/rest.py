"""REST handlers. Endpoints follow ADR-002; schemas follow contracts/rest/openapi.yaml."""
from fastapi import APIRouter, HTTPException, Request

from ..config import settings

router = APIRouter(prefix="/api/v1", tags=["arca-bench"])


def _service(request: Request):
    return request.app.state.bench_service


@router.get("/bench/health")
def api_health():
    return {"service": settings.app_name, "status": "ok"}


@router.get("/tests")
def list_tests(request: Request):
    return {"tests": [t.to_dict() for t in _service(request).list_tests()]}


@router.post("/tests", status_code=201)
def register_test(body: dict, request: Request):
    name = (body or {}).get("name")
    category = (body or {}).get("category")
    version = (body or {}).get("version", "1.0.0")
    if not name or not category:
        raise HTTPException(status_code=422, detail="name and category required")
    test = _service(request).register_test(name, category, version)
    return test.to_dict()


@router.post("/runs", status_code=202)
def start_run(body: dict, request: Request):
    target = (body or {}).get("target")
    suite = (body or {}).get("suite")
    if not target or not suite:
        raise HTTPException(status_code=422, detail="target and suite required")
    run = _service(request).start_run(target, suite)
    return {"run_id": run.id, "status": run.status.value,
            "correlation_id": run.id}


@router.get("/runs/{run_id}")
def get_run(run_id: str, request: Request):
    run = _service(request).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run_id": run.id, "target": run.target, "suite": run.suite,
            "status": run.status.value,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None}


@router.post("/runs/{run_id}/results", status_code=201)
def submit_result(run_id: str, body: dict, request: Request):
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
def complete_run(run_id: str, request: Request):
    try:
        return _service(request).complete_run(run_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="run not found")


@router.get("/scores")
def list_scores(target: str | None = None, request: Request = None):
    scores = _service(request).get_scores(target=target)
    return {"scores": [s.to_dict() for s in scores]}
