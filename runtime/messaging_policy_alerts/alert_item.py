from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MessagingPolicyAlertItem:
    code: str
    level: str
    title: str
    detail: str
    metric_name: str
    metric_value: float
    threshold_value: float
