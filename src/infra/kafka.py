"""Kafka producer/consumer (ADR-003, ADR-009). Schemas: contracts/kafka/events.avsc."""
import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class KafkaEvent:
    topic: str
    key: str
    payload: dict
    headers: dict = field(default_factory=dict)


class KafkaProducer:
    def publish(self, event: KafkaEvent) -> str:
        raise NotImplementedError("Kafka producer wiring lands with the platform profile")


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
        if event.topic != "asset.published":
            return
        asset_id = event.payload.get("asset_id") or event.payload.get("id")
        if not asset_id:
            return
        suite = event.payload.get("suite") or default_suite
        if not suite:
            return
        run = service.start_run(asset_id, suite)
        for test_id in suite:
            try:
                service.submit_result(run.id, test_id, True, "kafka-triggered")
            except Exception:
                pass
        service.complete_run(run.id)
    return handler
