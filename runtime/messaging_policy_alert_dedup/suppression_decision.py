from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AlertSuppressionDecision:
    should_send: bool
    reason: str
