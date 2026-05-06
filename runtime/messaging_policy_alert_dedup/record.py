from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AlertNotificationDedupRecord:
    dedup_key: str
    sent_at_epoch_s: int
