from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MatchedSubscription:
    recipient_user_id: str
    channel: str
    alert_code: str
    alert_level: str
    affected_user_id: str
