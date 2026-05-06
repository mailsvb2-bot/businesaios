from __future__ import annotations

from typing import Protocol

from runtime.messaging_policy_readmodel.snapshot_record import MessagingPolicySnapshotRecord


class MessagingPolicySnapshotStore(Protocol):
    def get(
        self,
        *,
        tenant_id: str,
        user_id: str,
        correlation_id: str,
    ) -> MessagingPolicySnapshotRecord | None:
        ...

    def put(self, record: MessagingPolicySnapshotRecord) -> None:
        ...
