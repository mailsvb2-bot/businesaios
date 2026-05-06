from __future__ import annotations

from threading import Lock

from runtime.messaging_policy_readmodel.snapshot_key import build_snapshot_key
from runtime.messaging_policy_readmodel.snapshot_record import MessagingPolicySnapshotRecord


class InMemoryMessagingPolicySnapshotStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._items: dict[tuple[str, str, str], MessagingPolicySnapshotRecord] = {}

    def get(
        self,
        *,
        tenant_id: str,
        user_id: str,
        correlation_id: str,
    ) -> MessagingPolicySnapshotRecord | None:
        key = build_snapshot_key(tenant_id=tenant_id, user_id=user_id, correlation_id=correlation_id)
        with self._lock:
            return self._items.get(key)

    def put(self, record: MessagingPolicySnapshotRecord) -> None:
        key = build_snapshot_key(tenant_id=record.tenant_id, user_id=record.user_id, correlation_id=record.correlation_id)
        with self._lock:
            self._items[key] = record
