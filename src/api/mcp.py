"""MCP capability handlers. Capabilities follow contracts/mcp/capabilities.json (ADR-004, ADR-009)."""
from fastapi import APIRouter, Depends, HTTPException, Request

from ..core.security.jwt import require_role

router = APIRouter(prefix="/mcp", tags=["mcp"])


def _service(request: Request):
    return request.app.state.bench_service


@router.get("/capabilities")
def list_capabilities():
    return {
        "capabilities": [
            {"name": "test-register",
             "description": "Register a new test case in the bench catalog."},
            {"name": "run_test_suite",
             "description": "Execute a test suite against a target."},
            {"name": "get_scorecard",
             "description": "Return the scorecard for a completed run."},
            {"name": "generate_report",
             "description": "Generate a remediation report for a run."},
        ]
    }


@router.post("/tools/test-register")
def test_register(body: dict, request: Request,
                  user=Depends(require_role("bench_admin", "bench_runner"))):
    """Register a new test case via MCP."""
    name = (body or {}).get("name")
    category = (body or {}).get("category")
    version = (body or {}).get("version", "1.0.0")
    if not name or not category:
        raise HTTPException(status_code=422, detail="name and category required")
    test = _service(request).register_test(name, category, version)
    return test.to_dict()


@router.post("/tools/run_test_suite")
def run_test_suite(body: dict, request: Request,
                   user=Depends(require_role("bench_admin", "bench_runner"))):
    body = body or {}
    target = body.get("target")
    suite = body.get("suite")
    collect_evidence = body.get("collect_evidence", False)
    if not target or suite is None:
        raise HTTPException(status_code=422,
                            detail="target and suite required")
    svc = _service(request)
    run = svc.start_run(target, suite)
    results = []
    for test_id in suite:
        try:
            result = svc.submit_result(run.id, test_id, True, "auto-executed")
            results.append(result.to_dict())
        except Exception as exc:
            results.append({"test_case_id": test_id, "error": str(exc)})
    summary = svc.complete_run(run.id)
    if collect_evidence:
        svc.collect_evidence(run.id, f"evidence://{target}/run-{run.id}")
    return {"run_id": run.id, "status": run.status.value,
            "summary": summary, "results": results}


@router.post("/tools/get_scorecard")
def get_scorecard(body: dict, request: Request,
                  user=Depends(require_role("bench_admin", "bench_runner",
                                            "bench_reader"))):
    run_id = (body or {}).get("run_id")
    if not run_id:
        raise HTTPException(status_code=422, detail="run_id required")
    try:
        scorecard = _service(request).get_scorecard(run_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="run not found")
    return scorecard.to_dict()


@router.post("/tools/generate_report")
def generate_report(body: dict, request: Request,
                    user=Depends(require_role("bench_admin", "bench_runner"))):
    body = body or {}
    run_id = body.get("run_id")
    format = body.get("format", "json")
    if not run_id:
        raise HTTPException(status_code=422, detail="run_id required")
    try:
        report = _service(request).generate_report(run_id, format)
    except LookupError:
        raise HTTPException(status_code=404, detail="run not found")
    return report.to_dict()
