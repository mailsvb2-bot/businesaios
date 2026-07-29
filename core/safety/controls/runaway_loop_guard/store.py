from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from threading import RLock
from typing import Protocol

from compatibility.safety_storage_exports import resolve_safety_storage_export

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


def __getattr__(name: str):
    return resolve_safety_storage_export("runaway_loop", name)
__all__ = [
    'CANON_PLATFORM_SAFETY_RUNAWAY_LOOP_STORE',
    'CANON_SAFETY_RUNAWAY_LOOP_STORE',
    'InMemoryRunawayLoopStore',
    'RunawayLoopStore',
    'SCHEMA_VERSION',
    'SqliteRunawayLoopStore',
]
