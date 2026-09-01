from __future__ import annotations

from runtime.messaging_policy_alert_dedup.record import AlertNotificationDedupRecord
from runtime.messaging_policy_alert_dedup.time_now import now_epoch_s


class TenantAwareAlertNotificationMarkSentService:
    def __init__(self, *, store_factory):
        self._store_factory = store_factory

    def mark_sent(self, *, tenant_id: str, dedup_key: str) -> None:
        self._store_factory.for_tenant(tenant_id=tenant_id).put(AlertNotificationDedupRecord(dedup_key=str(dedup_key), sent_at_epoch_s=int(now_epoch_s())))

    def mark_pending(self, *, tenant_id: str, dedup_key: str, approval_id: str) -> None:
        approval_key = str(approval_id or "").strip()
        if not approval_key:
            return
        store = self._store_factory.for_tenant(tenant_id=tenant_id)
        store.put(AlertNotificationDedupRecord(dedup_key=str(dedup_key), sent_at_epoch_s=0, pending_approval_id=approval_key))
        store.bind_pending_approval(approval_id=approval_key, dedup_key=str(dedup_key))

    def finalize_approval(self, *, tenant_id: str, approval_id: str) -> bool:
        approval_key = str(approval_id or "").strip()
        store = self._store_factory.for_tenant(tenant_id=tenant_id)
        dedup_key = store.dedup_key_for_approval(approval_id=approval_key)
        record = store.get(dedup_key=dedup_key) if dedup_key else None
        if record is None or str(record.pending_approval_id) != approval_key:
            return False
        self.mark_sent(tenant_id=tenant_id, dedup_key=dedup_key)
        return True
