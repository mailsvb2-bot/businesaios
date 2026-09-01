from __future__ import annotations

from runtime.messaging_policy_alert_dedup.record import AlertNotificationDedupRecord
from runtime.messaging_policy_alert_dedup.time_now import now_epoch_s


class AlertNotificationMarkSentService:
    def __init__(self, *, store):
        self._store = store

    def mark_sent(self, *, dedup_key: str) -> None:
        self._store.put(AlertNotificationDedupRecord(dedup_key=str(dedup_key), sent_at_epoch_s=now_epoch_s()))

    def mark_pending(self, *, dedup_key: str, approval_id: str) -> None:
        approval_key = str(approval_id or "").strip()
        if not approval_key:
            return
        self._store.put(AlertNotificationDedupRecord(dedup_key=str(dedup_key), sent_at_epoch_s=0, pending_approval_id=approval_key))
        self._store.bind_pending_approval(approval_id=approval_key, dedup_key=str(dedup_key))

    def finalize_approval(self, *, approval_id: str) -> bool:
        approval_key = str(approval_id or "").strip()
        dedup_key = self._store.dedup_key_for_approval(approval_id=approval_key)
        record = self._store.get(dedup_key=dedup_key) if dedup_key else None
        if record is None or str(record.pending_approval_id) != approval_key:
            return False
        self.mark_sent(dedup_key=dedup_key)
        return True
