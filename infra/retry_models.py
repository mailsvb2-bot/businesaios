from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicySpec:
    max_attempts: int
    delay_seconds: float
