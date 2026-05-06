from __future__ import annotations

from core.behavior.contracts.snapshots import SegmentFieldSnapshot
from core.behavior.persistence.in_memory_snapshot_store import InMemorySnapshotStore


class SegmentSnapshotRepository:
    def __init__(self, store: InMemorySnapshotStore[SegmentFieldSnapshot]) -> None:
        self._store = store

    def save(self, snapshot: SegmentFieldSnapshot) -> None:
        self._store.put(snapshot.snapshot_id, snapshot)

    def get(self, snapshot_id: str) -> SegmentFieldSnapshot | None:
        return self._store.get(snapshot_id)
