from __future__ import annotations

from runtime.tenancy import normalize_tenant_scope


class MessagingPolicyReadService:
    def __init__(self, *, repository, rebuild_service=None):
        self._repository = repository
        self._rebuild_service = rebuild_service

    def get_snapshot(self, *, tenant_id: str, user_id: str, correlation_id: str):
        tenant_scope = normalize_tenant_scope(tenant_id, allow_unknown=True)
        snap = self._repository.get(tenant_id=tenant_scope, user_id=str(user_id), correlation_id=str(correlation_id))
        if snap is not None:
            return snap
        if self._rebuild_service is None:
            return None
        return self._rebuild_service.rebuild_one(tenant_id=tenant_scope, user_id=str(user_id), correlation_id=str(correlation_id))
