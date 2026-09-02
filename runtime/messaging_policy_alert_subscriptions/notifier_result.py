from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AlertNotifierResult:
    notifications_total: int
    notifications_sent: int
    pending_approval_ids: tuple[str, ...] = ()
    notifications_ambiguous: int = 0
    notifications_terminal_failed: int = 0
