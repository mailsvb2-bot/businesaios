from __future__ import annotations

from runtime.messaging_policy_alert_dedup_persistent.store import PersistentAlertNotificationDedupStore
from runtime.tenancy import normalize_tenant_scope


class TenantScopedDedupStoreFactory:
    def __init__(self, *, settings_gateway):
        self._settings_gateway = settings_gateway

    def for_tenant(self, *, tenant_id: str):
        return PersistentAlertNotificationDedupStore(
            settings_gateway=self._settings_gateway,
            tenant_id=normalize_tenant_scope(tenant_id, allow_unknown=True),
        )
