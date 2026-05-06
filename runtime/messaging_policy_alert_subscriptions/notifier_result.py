from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AlertNotifierResult:
    notifications_total: int
    notifications_sent: int
