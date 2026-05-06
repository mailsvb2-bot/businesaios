from __future__ import annotations

from runtime.tenancy import normalize_tenant_scope


class MessagingPolicySnapshotRepository:
    def __init__(self, *, store):
        self._store = store

    def get(self, *, tenant_id: str, user_id: str, correlation_id: str):
        return self._store.get(
            tenant_id=normalize_tenant_scope(tenant_id, allow_unknown=True),
            user_id=str(user_id),
            correlation_id=str(correlation_id),
        )

    def put(self, record) -> None:
        self._store.put(record)


MessagingPolicyReadRepository = MessagingPolicySnapshotRepository
