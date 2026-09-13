"""Application entry point."""
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import graphql, mcp, rest
from .config import settings
from .core.events.bench_events import KafkaDomainEventPublisher
from .core.services.bench_service import BenchService
from .infra import otel
from .infra.kafka import KafkaConsumer, KafkaProducer, build_asset_published_handler
from .infra.soc import EmbeddedSOC
from .infra.store import SqlBenchRepository, connect_sqlite


@asynccontextmanager
async def lifespan(app: FastAPI):
    repository = SqlBenchRepository(connect_sqlite())
    soc = EmbeddedSOC()
    app.state.soc = soc
    app.state.bench_repository = repository
    kafka_producer = KafkaProducer(settings.kafka_bootstrap_servers)
    app.state.kafka_producer = kafka_producer
    publisher = KafkaDomainEventPublisher(kafka_producer)
    app.state.bench_service = BenchService(repository, publisher=publisher, soc=soc)

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


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
otel.instrument(app)

app.include_router(rest.router)
app.include_router(mcp.router)
app.include_router(graphql.graphql_router, prefix="/graphql")
app.mount("/ui", StaticFiles(directory="src/ui", html=True), name="ui")


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": settings.app_name}


@app.get("/readyz")
def readyz():
    return {"status": "ready"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
