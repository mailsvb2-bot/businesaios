from __future__ import annotations

from threading import Lock

from runtime.messaging_policy_alert_dedup.record import AlertNotificationDedupRecord


class InMemoryAlertNotificationDedupStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._items: dict[str, AlertNotificationDedupRecord] = {}

    def get(self, *, dedup_key: str) -> AlertNotificationDedupRecord | None:
        with self._lock:
            return self._items.get(str(dedup_key))

    def put(self, record: AlertNotificationDedupRecord) -> None:
        with self._lock:
            self._items[str(record.dedup_key)] = record
