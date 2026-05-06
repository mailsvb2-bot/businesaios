from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AlertNotificationItem:
    tenant_id: str
    recipient_user_id: str
    channel: str
    text: str
    alert_code: str
    alert_level: str
    affected_user_id: str
