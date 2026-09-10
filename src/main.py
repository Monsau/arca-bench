"""Application entry point."""
import os

from fastapi import FastAPI

from .api import mcp, rest
from .config import settings
from .core.services.bench_service import BenchService
from .infra import otel
from .infra.store import SqlBenchRepository, connect_sqlite

app = FastAPI(title=settings.app_name, version="0.1.0")
otel.instrument(app)


@app.on_event("startup")
def bind_services():
    repository = SqlBenchRepository(connect_sqlite())
    app.state.bench_service = BenchService(repository)
    app.state.bench_repository = repository


app.include_router(rest.router)
app.include_router(mcp.router)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": settings.app_name}


@app.get("/readyz")
def readyz():
    return {"status": "ready"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
