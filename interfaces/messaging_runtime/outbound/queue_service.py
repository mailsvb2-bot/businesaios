from __future__ import annotations

from .backpressure import QueueBackpressureGuard
from .stores import DurableOutboundQueueStore


class DurableOutboundQueueService:
    def __init__(self, *, store: DurableOutboundQueueStore, guard: QueueBackpressureGuard) -> None:
        self._store = store
        self._guard = guard

    def enqueue(self, envelope) -> bool:
        self._guard.check(self._store.size())
        return self._store.put(envelope)

    def dequeue(self):
        return self._store.get()

    def size(self) -> int:
        return self._store.size()

    def release(self, dedupe_key: str) -> None:
        self._store.release(dedupe_key)
