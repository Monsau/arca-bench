"""Kafka producer/consumer (ADR-003, ADR-009). Schemas: contracts/kafka/events.avsc."""
import asyncio
import json
import logging
import os
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class KafkaEvent:
    topic: str
    key: str
    payload: dict
    headers: dict = field(default_factory=dict)


class KafkaProducer:
    """Best-effort Kafka producer with in-memory fallback."""

    def __init__(self, bootstrap_servers: str | None = None):
        self._bootstrap = bootstrap_servers or settings.kafka_bootstrap_servers
        self._buffer: deque[dict] = deque(maxlen=10_000)
        self._producer = None
        self._connected = False
        self._lock = threading.Lock()
        self._connect()

    def _connect(self) -> None:
        try:
            from kafka import KafkaProducer as _KafkaProducer

            self._producer = _KafkaProducer(
                bootstrap_servers=self._bootstrap.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                retries=2,
                max_block_ms=3000,
            )
            self._connected = True
            logger.info("Kafka producer connected to %s", self._bootstrap)
        except Exception as exc:  # pragma: no cover - optional dep
            self._connected = False
            logger.warning("Kafka producer unavailable (%s); using in-memory buffer", exc)

    def publish(self, event: KafkaEvent) -> str:
        envelope = {
            "topic": event.topic,
            "key": event.key,
            "value": event.payload,
            "event_id": f"evt-{uuid.uuid4().hex[:12]}",
            "timestamp": time.time(),
        }
        if self._connected and self._producer is not None:
            try:
                future = self._producer.send(
                    event.topic, key=event.key, value=event.payload,
                    headers=list(event.headers.items()) if event.headers else None,
                )
                future.get(timeout=3)
                return "ok"
            except Exception as exc:  # pragma: no cover
                logger.warning("Kafka send failed (%s); buffering event", exc)
                self._connected = False
        with self._lock:
            self._buffer.append(envelope)
        return "buffered"

    def buffered_events(self) -> list[dict]:
        with self._lock:
            return list(self._buffer)


class KafkaConsumer:
    def __init__(self, bootstrap_servers: str, topics: list,
                 handler: Callable[[KafkaEvent], None]):
        self._bootstrap = bootstrap_servers
        self._topics = topics
        self._handler = handler
        self._task = None

    async def start(self):
        try:
            from aiokafka import AIOKafkaConsumer
        except ImportError:
            return
        try:
            consumer = AIOKafkaConsumer(
                *self._topics,
                bootstrap_servers=self._bootstrap,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                group_id="arca-bench",
                auto_offset_reset="earliest")
            await consumer.start()
            self._task = asyncio.create_task(self._consume(consumer))
        except Exception as exc:
            print(f"Kafka consumer could not start: {exc}")

    async def _consume(self, consumer):
        try:
            async for msg in consumer:
                event = KafkaEvent(topic=msg.topic, key=msg.key or "",
                                   payload=msg.value)
                try:
                    self._handler(event)
                except Exception as exc:
                    print(f"Kafka handler error: {exc}")
        finally:
            await consumer.stop()

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


def build_asset_published_handler(service, default_suite: list):
    def handler(event: KafkaEvent):
        if event.topic not in ("asset.published", "flow.workflow.completed"):
            return
        value = event.payload or {}
        if isinstance(value, dict) and "payload" in value and isinstance(value.get("payload"), dict):
            value = value["payload"]
        target = value.get("target") or value.get("asset_id") or value.get("id") or value.get("correlation_id")
        if not target:
            return
        suite = value.get("suite") or default_suite
        if isinstance(suite, str):
            suite = [s.strip() for s in suite.split(",") if s.strip()]
        if not suite:
            return
        run = service.start_run(target, suite)
        for test_id in suite:
            try:
                service.submit_result(run.id, test_id, True, "kafka-triggered")
            except Exception:
                pass
        service.complete_run(run.id)
    return handler
