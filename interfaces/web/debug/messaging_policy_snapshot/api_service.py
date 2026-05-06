from __future__ import annotations

from runtime.messaging_policy_readmodel.read_api import read_messaging_policy_snapshot


class MessagingPolicySnapshotAPIService:
    def __init__(self, *, read_service):
        self._read_service = read_service

    def get_snapshot(self, *, tenant_id: str, user_id: str, correlation_id: str) -> dict | None:
        return read_messaging_policy_snapshot(
            read_service=self._read_service,
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            correlation_id=str(correlation_id),
        )
