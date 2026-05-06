from __future__ import annotations

from core.behavior.contracts.snapshots import OrgFieldSnapshot
from core.behavior.persistence.in_memory_snapshot_store import InMemorySnapshotStore


class OrgSnapshotRepository:
    def __init__(self, store: InMemorySnapshotStore[OrgFieldSnapshot]) -> None:
        self._store = store

    def save(self, snapshot: OrgFieldSnapshot) -> None:
        self._store.put(snapshot.snapshot_id, snapshot)

    def get(self, snapshot_id: str) -> OrgFieldSnapshot | None:
        return self._store.get(snapshot_id)
