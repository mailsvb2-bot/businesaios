from __future__ import annotations

from core.behavior.contracts.snapshots import PersonFieldSnapshot
from core.behavior.persistence.in_memory_snapshot_store import InMemorySnapshotStore


class PersonSnapshotRepository:
    def __init__(self, store: InMemorySnapshotStore[PersonFieldSnapshot]) -> None:
        self._store = store

    def save(self, snapshot: PersonFieldSnapshot) -> None:
        self._store.put(snapshot.snapshot_id, snapshot)

    def get(self, snapshot_id: str) -> PersonFieldSnapshot | None:
        return self._store.get(snapshot_id)
