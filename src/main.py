"""Application entry point."""
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.staticfiles import StaticFiles

from .api import graphql, mcp, rest
from .config import settings
from .core.events.bench_events import KafkaDomainEventPublisher
from .core.security.jwt import get_current_user
from .core.services.bench_service import BenchService
from .infra import metrics, otel, opa
from .infra.kafka import KafkaConsumer, KafkaProducer, build_asset_published_handler
from .infra.soc import EmbeddedSOC
from .infra.store import SqlBenchRepository, connect_sqlite


@asynccontextmanager
async def lifespan(app: FastAPI):
    # OPA/Rego mode: execute bench.rego through an OPA runner when one
    # exists; otherwise the Rego file is strictly informative (enforcement
    # stays in the Python RBAC/ABAC stack). Always announced with one log line.
    opa.log_policy_mode()    # Backend selection: DATABASE_URL (injected from bench-secrets) selects
    # the shared PostgreSQL store so all replicas see the same runs; without
    # it we fall back to in-memory SQLite for dev/tests.
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        repository = SqlBenchRepository(database_url)
    else:
        repository = SqlBenchRepository(connect_sqlite())
    soc = EmbeddedSOC()
    app.state.soc = soc
    app.state.bench_repository = repository
    kafka_producer = KafkaProducer(settings.kafka_bootstrap_servers)
    app.state.kafka_producer = kafka_producer
    publisher = KafkaDomainEventPublisher(kafka_producer)
    app.state.bench_service = BenchService(repository, publisher=publisher, soc=soc)

    from .core.services.decision_replay import DecisionReplayBench
    replay_bench = DecisionReplayBench()

    def _threshold_rule(inputs: dict):
        """Reference deterministic rule for replay: outcome = amount >= limit."""
        return inputs.get("amount", 0) >= inputs.get("limit", 0)

    replay_bench.register_rule("threshold", _threshold_rule)
    app.state.decision_replay = replay_bench

    default_suite = os.environ.get("BENCH_DEFAULT_SUITE", "").split(",")
    default_suite = [s.strip() for s in default_suite if s.strip()]
    consumer = KafkaConsumer(
        settings.kafka_bootstrap_servers,
        ["asset.published", "flow.workflow.completed"],
        build_asset_published_handler(app.state.bench_service, default_suite))
    app.state.kafka_consumer = consumer
    await consumer.start()

    yield

    await consumer.stop()


def _docs_metadata_guard(request: Request) -> None:
    """Zero Trust gate for the API metadata endpoints (/docs, /redoc,
    /openapi.json).

    Dev/standalone keeps them open (module dev-gate convention); every other
    environment requires a valid Keycloak JWT through the existing JWKS/RS256
    stack (ADR-009). The endpoints are re-served below with this guard — they
    are protected, not hidden. Health endpoints stay open for k8s probes.
    """
    if settings.environment == "dev":
        return
    get_current_user(request)


app = FastAPI(
    title=settings.app_name,
    version="2.3.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
otel.instrument(app)
# Prometheus HTTP middleware: request count + latency per route template.
app.add_middleware(metrics.PrometheusMiddleware)

app.include_router(rest.router)
app.include_router(mcp.router)
app.include_router(graphql.graphql_router, prefix="/graphql")
app.mount("/ui", StaticFiles(directory="src/ui", html=True), name="ui")


@app.get("/openapi.json", include_in_schema=False)
async def openapi_json(_: None = Depends(_docs_metadata_guard)):
    return app.openapi()


@app.get("/docs", include_in_schema=False)
async def swagger_ui(_: None = Depends(_docs_metadata_guard)):
    return get_swagger_ui_html(
        openapi_url="/openapi.json", title=f"{settings.app_name} - Swagger UI"
    )


@app.get("/redoc", include_in_schema=False)
async def redoc_ui(_: None = Depends(_docs_metadata_guard)):
    return get_redoc_html(
        openapi_url="/openapi.json", title=f"{settings.app_name} - ReDoc"
    )


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": settings.app_name}


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics():
    # /metrics is UNAUTHENTICATED by design: it is exposed cluster-internally
    # only, and NetworkPolicy restricts scraping to the external observability
    # stack. This route is deliberately NOT covered by the
    # _docs_metadata_guard above — only /docs, /redoc and /openapi.json are.
    return metrics.metrics_response()


@app.get("/readyz")
def readyz():
    return {"status": "ready"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
