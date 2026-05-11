from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from threading import RLock
from typing import Protocol

from runtime.platform.safety_runaway_loop_store import (
    CANON_PLATFORM_SAFETY_RUNAWAY_LOOP_STORE,
    PlatformSqliteRunawayLoopStore,
    SCHEMA_VERSION,
)

CANON_SAFETY_RUNAWAY_LOOP_STORE = True


class RunawayLoopStore(Protocol):
    def append(self, tenant_id: str, fingerprint: str) -> tuple[str, ...]: ...


@dataclass
class InMemoryRunawayLoopStore:
    recent: dict[str, deque[str]] = field(default_factory=dict)
    maxlen: int = 5
    _lock: RLock = field(default_factory=RLock)

    def append(self, tenant_id: str, fingerprint: str) -> tuple[str, ...]:
        with self._lock:
            bucket = self.recent.setdefault(str(tenant_id), deque(maxlen=self.maxlen))
            bucket.append(str(fingerprint))
            return tuple(bucket)


class SqliteRunawayLoopStore(PlatformSqliteRunawayLoopStore):
    """Safety-facing runaway-loop store facade.

    SQLite ownership lives in runtime.platform.safety_runaway_loop_store.
    """


__all__ = [
    'CANON_PLATFORM_SAFETY_RUNAWAY_LOOP_STORE',
    'CANON_SAFETY_RUNAWAY_LOOP_STORE',
    'InMemoryRunawayLoopStore',
    'RunawayLoopStore',
    'SCHEMA_VERSION',
    'SqliteRunawayLoopStore',
]
