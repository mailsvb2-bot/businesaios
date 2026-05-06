from __future__ import annotations

from typing import Optional, Protocol


class SnapshotStore(Protocol):
    """Snapshot storage port.

    Ring Spec Block 4:
      - Decision must be bound to a versioned, canonical snapshot of WorldState
      - snapshot_id is included in the signature

    Implementations:
      - observability.platform.snapshot_store.postgres_snapshot_store.PostgresSnapshotStore (prod)
      - observability.platform.snapshot_store.sqlite_snapshot_store.SqliteSnapshotStore (dev)
    """

    def put(self, snapshot_id: str, canonical_bytes: bytes) -> None:  # pragma: no cover
        ...

    def get(self, snapshot_id: str) -> Optional[bytes]:  # pragma: no cover
        ...


class MemorySnapshotStore:
    """Test-only snapshot store."""

    def __init__(self):
        self._data: dict[str, bytes] = {}

    def put(self, snapshot_id: str, canonical_bytes: bytes) -> None:
        self._data[str(snapshot_id)] = bytes(canonical_bytes)

    def get(self, snapshot_id: str) -> Optional[bytes]:
        return self._data.get(str(snapshot_id))
