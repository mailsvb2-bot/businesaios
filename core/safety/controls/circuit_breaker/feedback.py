from __future__ import annotations

from .models import CircuitBreakerState
from .store import CircuitBreakerStore


class CircuitBreakerFeedback:
    def __init__(self, store: CircuitBreakerStore, threshold: int) -> None:
        self._store = store
        self._threshold = max(1, int(threshold or 1))

    def record_success(self, key: str) -> None:
        self._store.put(CircuitBreakerState(key=str(key), consecutive_failures=0, opened=False))

    def record_failure(self, key: str) -> None:
        current = self._store.get(str(key))
        failures = int(current.consecutive_failures) + 1
        self._store.put(
            CircuitBreakerState(
                key=str(key),
                consecutive_failures=failures,
                opened=failures >= self._threshold,
            )
        )
