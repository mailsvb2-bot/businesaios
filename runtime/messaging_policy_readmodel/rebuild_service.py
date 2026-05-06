from __future__ import annotations

from runtime.tenancy import normalize_tenant_scope


class MessagingPolicyRebuildService:
    def __init__(self, *, event_store, projector, repository=None):
        self._event_store = event_store
        self._projector = projector
        self._repository = repository

    def rebuild_one(self, *, tenant_id: str, user_id: str, correlation_id: str):
        tenant_scope = normalize_tenant_scope(tenant_id, allow_unknown=True)
        records = self._event_store.read(
            tenant_id=tenant_scope,
            user_id=str(user_id),
            correlation_id=str(correlation_id),
        )
        if not records:
            return None
        snap = self._projector.project(records)
        if snap is not None and self._repository is not None and hasattr(self._repository, 'put'):
            self._repository.put(snap)
        return snap


MessagingPolicyReadRebuildService = MessagingPolicyRebuildService
