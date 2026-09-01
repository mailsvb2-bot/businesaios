from __future__ import annotations

from threading import Lock

from runtime.messaging_policy_alert_dedup.record import AlertNotificationDedupRecord


class InMemoryAlertNotificationDedupStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._items: dict[str, AlertNotificationDedupRecord] = {}
        self._approval_keys: dict[str, str] = {}

    def get(self, *, dedup_key: str) -> AlertNotificationDedupRecord | None:
        with self._lock:
            return self._items.get(str(dedup_key))

    def put(self, record: AlertNotificationDedupRecord) -> None:
        with self._lock:
            self._items[str(record.dedup_key)] = record

    def bind_pending_approval(self, *, approval_id: str, dedup_key: str) -> None:
        with self._lock:
            self._approval_keys[str(approval_id)] = str(dedup_key)

    def dedup_key_for_approval(self, *, approval_id: str) -> str:
        with self._lock:
            return str(self._approval_keys.get(str(approval_id)) or "")
