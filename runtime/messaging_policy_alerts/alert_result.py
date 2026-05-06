from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MessagingPolicyAlertResult:
    alerts: tuple
    traces_total: int
