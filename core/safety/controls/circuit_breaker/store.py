from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Protocol

from runtime.platform.safety_circuit_breaker_store import (
    CANON_PLATFORM_SAFETY_CIRCUIT_BREAKER_STORE,
    PlatformSqliteCircuitBreakerStore,
    SCHEMA_VERSION,
)

from .models import CircuitBreakerState

CANON_SAFETY_CIRCUIT_BREAKER_STORE = True


class CircuitBreakerStore(Protocol):
    def get(self, key: str) -> CircuitBreakerState: ...
    def put(self, state: CircuitBreakerState) -> None: ...


@dataclass
class InMemoryCircuitBreakerStore:
    states: dict[str, CircuitBreakerState] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def get(self, key: str) -> CircuitBreakerState:
        with self._lock:
            return self.states.get(str(key), CircuitBreakerState(key=str(key)))

    def put(self, state: CircuitBreakerState) -> None:
        with self._lock:
            self.states[str(state.key)] = state


class SqliteCircuitBreakerStore(PlatformSqliteCircuitBreakerStore):
    """Safety-facing circuit-breaker store facade.

    SQLite ownership lives in runtime.platform.safety_circuit_breaker_store.
    """


__all__ = [
    'CANON_PLATFORM_SAFETY_CIRCUIT_BREAKER_STORE',
    'CANON_SAFETY_CIRCUIT_BREAKER_STORE',
    'CircuitBreakerStore',
    'InMemoryCircuitBreakerStore',
    'SCHEMA_VERSION',
    'SqliteCircuitBreakerStore',
]
