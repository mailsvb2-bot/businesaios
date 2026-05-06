from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DedupAlertNotifierResult:
    notifications_total: int
    notifications_sent: int
    notifications_suppressed: int
