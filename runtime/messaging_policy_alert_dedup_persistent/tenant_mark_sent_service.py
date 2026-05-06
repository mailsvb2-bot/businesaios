from __future__ import annotations

from runtime.messaging_policy_alert_dedup.record import AlertNotificationDedupRecord
from runtime.messaging_policy_alert_dedup.time_now import now_epoch_s


class TenantAwareAlertNotificationMarkSentService:
    def __init__(self, *, store_factory):
        self._store_factory = store_factory

    def mark_sent(self, *, tenant_id: str, dedup_key: str) -> None:
        store = self._store_factory.for_tenant(tenant_id=tenant_id)
        store.put(
            AlertNotificationDedupRecord(
                dedup_key=str(dedup_key),
                sent_at_epoch_s=int(now_epoch_s()),
            )
        )
