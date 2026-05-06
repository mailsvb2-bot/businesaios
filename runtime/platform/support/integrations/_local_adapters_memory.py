from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from runtime.observability.metrics import Metrics


class ExperimentTrackerAdapter:
    """Small in-memory tracker for local experiment runs."""

    PLATFORM_SUPPORT_LOCAL = True

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def track(self, payload: Mapping[str, Any]) -> None:
        self._records.append(deepcopy(dict(payload)))

    def records(self) -> list[dict[str, Any]]:
        return [deepcopy(dict(item)) for item in self._records]


class FeatureStoreAdapter:
    """In-process feature store for local support flows."""

    PLATFORM_SUPPORT_LOCAL = True

    def __init__(self) -> None:
        self._features: dict[str, Any] = {}

    def put(self, key: str, value: Any) -> None:
        self._features[str(key)] = deepcopy(value)

    def fetch(self, key: str, default: Any | None = None) -> Any:
        value = self._features.get(str(key), default)
        return deepcopy(value)

    def fetch_many(self, keys: list[str]) -> dict[str, Any]:
        return {str(key): deepcopy(self._features[str(key)]) for key in keys if str(key) in self._features}


class MessageBusAdapter:
    """Append-only local message bus for offline workflows."""

    PLATFORM_SUPPORT_LOCAL = True

    def __init__(self) -> None:
        self._topics: dict[str, list[Any]] = {}

    def publish(self, topic: str, message: Any) -> None:
        topic_name = str(topic)
        self._topics.setdefault(topic_name, []).append(deepcopy(message))

    def messages(self, topic: str) -> list[Any]:
        return [deepcopy(item) for item in self._topics.get(str(topic), ())]

    def topics(self) -> tuple[str, ...]:
        return tuple(sorted(self._topics))


class MetricsAdapter:
    """Small adapter over the canonical runtime metrics owner."""

    PLATFORM_SUPPORT_LOCAL = True

    def __init__(self, metrics: Metrics | None = None) -> None:
        self._metrics = metrics or Metrics()

    def increment(self, name: str, value: float = 1.0) -> None:
        metric_name = str(name)
        current = self._metrics.snapshot().get(metric_name, 0.0)
        self._metrics.set(metric_name, current + float(value))

    def set(self, name: str, value: float) -> None:
        self._metrics.set(str(name), float(value))

    def get(self, name: str) -> float:
        return self._metrics.snapshot().get(str(name), 0.0)

    def snapshot(self) -> dict[str, float]:
        return self._metrics.snapshot()


class ObjectStoreAdapter:
    """In-memory object store for local tooling."""

    PLATFORM_SUPPORT_LOCAL = True

    def __init__(self) -> None:
        self._objects: dict[str, Any] = {}

    def put(self, key: str, value: Any) -> None:
        self._objects[str(key)] = deepcopy(value)

    def get(self, key: str, default: Any | None = None) -> Any:
        value = self._objects.get(str(key), default)
        return deepcopy(value)

    def delete(self, key: str) -> None:
        self._objects.pop(str(key), None)

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._objects))

__all__ = [
    "ExperimentTrackerAdapter",
    "FeatureStoreAdapter",
    "MessageBusAdapter",
    "MetricsAdapter",
    "ObjectStoreAdapter",
]
