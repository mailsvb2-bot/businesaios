from __future__ import annotations

from runtime.messaging_policy_alert_dedup.record import AlertNotificationDedupRecord
from runtime.messaging_policy_alert_dedup.time_now import now_epoch_s


class TenantAwareAlertNotificationMarkSentService:
    def __init__(self, *, store_factory):
        self._store_factory = store_factory

    @staticmethod
    def _reservation_id(value: str) -> str:
        return f"reservation:{str(value or '').strip()}"

    def reserve(self, *, tenant_id: str, dedup_key: str, expected_record, reservation_id: str) -> bool:
        store = self._store_factory.for_tenant(tenant_id=tenant_id)
        target = AlertNotificationDedupRecord(dedup_key=str(dedup_key), sent_at_epoch_s=int(now_epoch_s()), pending_approval_id=self._reservation_id(reservation_id))
        return store.compare_and_set(expected=expected_record, record=target)

    def mark_sent(self, *, tenant_id: str, dedup_key: str, reservation_id: str = "") -> bool:
        store = self._store_factory.for_tenant(tenant_id=tenant_id)
        target = AlertNotificationDedupRecord(dedup_key=str(dedup_key), sent_at_epoch_s=int(now_epoch_s()))
        if not reservation_id:
            store.put(target)
            return True
        current = store.get(dedup_key=str(dedup_key))
        return bool(current and str(current.pending_approval_id) == self._reservation_id(reservation_id) and store.compare_and_set(expected=current, record=target))

    def mark_pending(self, *, tenant_id: str, dedup_key: str, approval_id: str, reservation_id: str = "") -> bool:
        approval_key = str(approval_id or "").strip()
        if not approval_key:
            return False
        store = self._store_factory.for_tenant(tenant_id=tenant_id)
        target = AlertNotificationDedupRecord(dedup_key=str(dedup_key), sent_at_epoch_s=0, pending_approval_id=approval_key)
        if not reservation_id:
            store.put(target)
            store.bind_pending_approval(approval_id=approval_key, dedup_key=str(dedup_key))
            return True
        current = store.get(dedup_key=str(dedup_key))
        expected = self._reservation_id(reservation_id)
        current_id = "" if current is None else str(current.pending_approval_id)
        return current_id == approval_key or bool(current and current_id == expected and store.compare_and_set(expected=current, record=target))

    def release(self, *, tenant_id: str, dedup_key: str, approval_id: str = "", reservation_id: str = "", ambiguous: bool = False) -> bool:
        store = self._store_factory.for_tenant(tenant_id=tenant_id)
        current = store.get(dedup_key=str(dedup_key))
        allowed = {str(approval_id or '').strip(), self._reservation_id(reservation_id) if reservation_id else ''}
        if current is None or str(current.pending_approval_id) not in allowed:
            return False
        return store.compare_and_set(expected=current, record=AlertNotificationDedupRecord(dedup_key=str(dedup_key), sent_at_epoch_s=0, pending_approval_id=f'ambiguous:{reservation_id}' if ambiguous else ''))
    def finalize_approval(self, *, tenant_id: str, approval_id: str, dedup_key: str = "", reservation_id: str = "", delivered: bool = True, ambiguous: bool = False) -> bool:
        approval_key = str(approval_id or "").strip()
        store = self._store_factory.for_tenant(tenant_id=tenant_id)
        key = str(dedup_key or '').strip() or store.dedup_key_for_approval(approval_id=approval_key)
        current = store.get(dedup_key=key) if key else None
        allowed = {approval_key, self._reservation_id(reservation_id) if reservation_id else ''}
        if current is None or str(current.pending_approval_id) not in allowed:
            return False
        target = AlertNotificationDedupRecord(dedup_key=key, sent_at_epoch_s=int(now_epoch_s()) if delivered else 0, pending_approval_id=f'ambiguous:{reservation_id or approval_key}' if ambiguous else '')
        return store.compare_and_set(expected=current, record=target)
