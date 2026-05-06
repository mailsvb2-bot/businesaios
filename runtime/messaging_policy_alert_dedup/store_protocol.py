from __future__ import annotations

from typing import Protocol

from runtime.messaging_policy_alert_dedup.record import AlertNotificationDedupRecord


class AlertNotificationDedupStore(Protocol):
    def get(self, *, dedup_key: str) -> AlertNotificationDedupRecord | None: ...
    def put(self, record: AlertNotificationDedupRecord) -> None: ...
