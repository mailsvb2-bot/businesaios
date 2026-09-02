from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AlertNotificationDedupRecord:
    dedup_key: str
    sent_at_epoch_s: int
    pending_approval_id: str = ""

    @property
    def is_pending(self) -> bool:
        return bool(str(self.pending_approval_id or "").strip())
