from __future__ import annotations

from core.behavior.contracts.snapshots import MarketFieldSnapshot
from core.behavior.persistence.in_memory_snapshot_store import InMemorySnapshotStore


class MarketSnapshotRepository:
    def __init__(self, store: InMemorySnapshotStore[MarketFieldSnapshot]) -> None:
        self._store = store

    def save(self, snapshot: MarketFieldSnapshot) -> None:
        self._store.put(snapshot.snapshot_id, snapshot)

    def get(self, snapshot_id: str) -> MarketFieldSnapshot | None:
        return self._store.get(snapshot_id)
