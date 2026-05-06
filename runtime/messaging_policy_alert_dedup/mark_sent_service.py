from __future__ import annotations

from runtime.messaging_policy_alert_dedup.record import AlertNotificationDedupRecord
from runtime.messaging_policy_alert_dedup.time_now import now_epoch_s


class AlertNotificationMarkSentService:
    def __init__(self, *, store):
        self._store = store

    def mark_sent(self, *, dedup_key: str) -> None:
        self._store.put(AlertNotificationDedupRecord(dedup_key=str(dedup_key), sent_at_epoch_s=now_epoch_s()))
