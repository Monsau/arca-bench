"""Kafka producer/consumer skeleton (ADR-003). Schemas: contracts/kafka/events.avsc."""
from dataclasses import dataclass, field


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
    def subscribe(self, topics: list) -> None:
        raise NotImplementedError("Kafka consumer wiring lands with the platform profile")
