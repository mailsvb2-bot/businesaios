from __future__ import annotations

from dataclasses import dataclass, field

from ..types import EconomicsSnapshot


@dataclass
class InMemoryEconomicsSnapshotRepository:
    _items: dict[str, EconomicsSnapshot] = field(default_factory=dict)
    _latest_snapshot_id: str | None = None

    def save(self, snapshot: EconomicsSnapshot) -> None:
        self._items[snapshot.snapshot_id.value] = snapshot
        self._latest_snapshot_id = snapshot.snapshot_id.value

    def get(self, snapshot_id: str) -> EconomicsSnapshot | None:
        return self._items.get(snapshot_id)

    def latest(self) -> EconomicsSnapshot | None:
        if self._latest_snapshot_id is None:
            return None
        return self._items.get(self._latest_snapshot_id)
