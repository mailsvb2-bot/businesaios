from __future__ import annotations

from core.world_model.ids import build_snapshot_key
from core.world_model.types import SnapshotRejection, WorldSnapshot


class InMemorySnapshotRepository:
    def __init__(self) -> None:
        self._latest: dict[str, WorldSnapshot] = {}
        self._history: dict[str, list[WorldSnapshot]] = {}
        self._rejections: list[SnapshotRejection] = []

    def put_snapshot(self, snapshot: WorldSnapshot) -> None:
        key = build_snapshot_key(tenant_id=snapshot.tenant_id, business_id=snapshot.business_id)
        self._latest[key] = snapshot
        self._history.setdefault(key, []).append(snapshot)

    def put_rejection(self, rejection: SnapshotRejection) -> None:
        self._rejections.append(rejection)

    def get_latest(self, *, tenant_id: str, business_id: str) -> WorldSnapshot | None:
        return self._latest.get(build_snapshot_key(tenant_id=tenant_id, business_id=business_id))

    def get_history(self, *, tenant_id: str, business_id: str) -> list[WorldSnapshot]:
        return list(self._history.get(build_snapshot_key(tenant_id=tenant_id, business_id=business_id), []))

    def list_rejections(self) -> list[SnapshotRejection]:
        return list(self._rejections)
