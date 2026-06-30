"""Delivery retry policy (retry/defer/dead_letter). Not a platform policy layer."""

from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class RetryDecision:
    action: str
    reason: str


class DeliveryRetryPolicy:
    def __init__(self, max_attempts: int = 3) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be > 0")
        self._max_attempts = max_attempts

    def evaluate(self, *, attempt_count: int, exc: Exception) -> RetryDecision:
        text = str(exc).lower()
        if attempt_count >= self._max_attempts:
            return RetryDecision("dead_letter", f"max_attempts:{attempt_count}")
        if "timeout" in text or "tempor" in text:
            return RetryDecision("retry", str(exc))
        if "429" in text or "rate" in text:
            return RetryDecision("defer", str(exc))
        return RetryDecision("dead_letter", str(exc))

    decide = evaluate
