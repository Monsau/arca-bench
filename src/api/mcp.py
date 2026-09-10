"""MCP capability handlers. Capabilities follow contracts/mcp/capabilities.json (ADR-004)."""
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/mcp", tags=["mcp"])


def _service(request: Request):
    return request.app.state.bench_service


@router.get("/capabilities")
def list_capabilities():
    return {"capabilities": ["test-register", "test-run", "score-compute"]}


@router.post("/tools/test-register")
def mcp_register(body: dict, request: Request):
    name = (body or {}).get("name")
    category = (body or {}).get("category")
    if not name or not category:
        raise HTTPException(status_code=422, detail="name and category required")
    return _service(request).register_test(name, category).to_dict()


@router.post("/tools/test-run")
def mcp_run(body: dict, request: Request):
    target = (body or {}).get("target")
    suite = (body or {}).get("suite")
    if not target or not suite:
        raise HTTPException(status_code=422, detail="target and suite required")
    run = _service(request).start_run(target, suite)
    return {"run_id": run.id, "status": run.status.value}


@router.post("/tools/score-compute")
def mcp_score(body: dict, request: Request):
    target = (body or {}).get("target")
    if not target:
        raise HTTPException(status_code=422, detail="target required")
    scores = _service(request).get_scores(target=target)
    return {"target": target, "scores": [s.to_dict() for s in scores]}
