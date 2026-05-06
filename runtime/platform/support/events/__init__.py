from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from observability.platform.telemetry.pubsub import AppendOnlyTopicLog

class EventPublisherContract(Protocol):
    def publish(self, topic: str, payload: dict) -> None:
        ...

class DeadLetterQueue:
    def __init__(self) -> None:
        self._items: list[dict] = []

    def push(self, payload: dict) -> None:
        self._items.append(dict(payload))

    def items(self) -> list[dict]:
        return list(self._items)

@dataclass(frozen=True)
class DeliveryGuarantees:
    at_least_once: bool = True

@dataclass(frozen=True)
class EventEnvelope:
    topic: str
    payload: Mapping[str, Any]

class EventBus:
    def __init__(self) -> None:
        self._topic_log = AppendOnlyTopicLog()

    def publish(self, topic: str, payload: dict) -> None:
        self._topic_log.append(topic, dict(payload))

    def events(self, topic: str) -> list[dict]:
        return self._topic_log.events(topic)

class EventDeserializer:
    def deserialize(self, payload: dict) -> EventEnvelope:
        return EventEnvelope(topic=str(payload["topic"]), payload=dict(payload["payload"]))

class EventSerializer:
    def serialize(self, envelope: EventEnvelope) -> dict:
        return {"topic": envelope.topic, "payload": dict(envelope.payload)}

EVENT_TYPES = (
    "rollout_completed",
    "evaluation_completed",
    "promotion_requested",
    "rollback_requested",
    "incident_detected",
)

class Idempotency:
    def __init__(self) -> None:
        self._keys: set[str] = set()

    def seen(self, key: str) -> bool:
        if key in self._keys:
            return True
        self._keys.add(key)
        return False

class Publisher:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    def publish(self, topic: str, payload: dict) -> None:
        self._bus.publish(topic, payload)

class RetryPolicy:
    def should_retry(self, attempts: int, max_attempts: int) -> bool:
        return attempts < max_attempts

class Subscriber:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    def read(self, topic: str) -> list[dict]:
        return self._bus.events(topic)

class TopicRegistry:
    def __init__(self) -> None:
        self._topics: set[str] = set()

    def register(self, topic: str) -> None:
        self._topics.add(topic)

    def exists(self, topic: str) -> bool:
        return topic in self._topics

__all__ = [
    "DeadLetterQueue",
    "DeliveryGuarantees",
    "EVENT_TYPES",
    "EventBus",
    "EventDeserializer",
    "EventEnvelope",
    "EventPublisherContract",
    "EventSerializer",
    "Idempotency",
    "Publisher",
    "RetryPolicy",
    "Subscriber",
    "TopicRegistry",
]
