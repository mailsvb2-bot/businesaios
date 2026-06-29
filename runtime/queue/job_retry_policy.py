"""Retry policy for runtime queue workers.

The policy is deliberately operational, not strategic.
It classifies errors only to decide retry delay / dead-letter outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import randint
from collections.abc import Iterable
from runtime.queue.job_contract import JobRecord

CANON_RUNTIME_QUEUE_RETRY_POLICY = True

@dataclass(frozen=True)
class JobRetryDecision:
    should_retry: bool
    delay_seconds: int
    move_to_dead_letter: bool
    reason: str
    error_family: str = "unknown"


class JobRetryPolicy:
    def __init__(
        self,
        *,
        base_delay_seconds: int = 10,
        max_delay_seconds: int = 1800,
        jitter_seconds: int = 3,
        terminal_error_markers: tuple[str, ...] = (
            "PERMISSION_DENIED",
            "SCHEMA_INVALID",
            "UNSUPPORTED_JOB_TYPE",
            "NON_RETRYABLE",
            "AUTH_INVALID",
            "VALIDATION_ERROR",
            "CANCELLED",
            "CANCELED",
            "KEYBOARDINTERRUPT",
            "NOTIMPLEMENTED",
        ),
        transient_error_markers: tuple[str, ...] = (
            "TIMEOUT",
            "TEMPORARY",
            "RATE_LIMIT",
            "UNAVAILABLE",
            "CONNECTION_RESET",
            "TOO_MANY_REQUESTS",
        ),
    ) -> None:
        self._base_delay_seconds = max(1, int(base_delay_seconds))
        self._max_delay_seconds = max(self._base_delay_seconds, int(max_delay_seconds))
        self._jitter_seconds = max(0, int(jitter_seconds))
        self._terminal_error_markers = tuple(str(item).upper() for item in terminal_error_markers)
        self._transient_error_markers = tuple(str(item).upper() for item in transient_error_markers)

    def _contains_any(self, message: str, markers: Iterable[str]) -> bool:
        return any(marker in message for marker in markers)

    def _error_family(self, message: str) -> str:
        if self._contains_any(message, self._terminal_error_markers):
            if "AUTH" in message or "PERMISSION" in message:
                return "authorization"
            if "VALIDATION" in message or "SCHEMA" in message:
                return "validation"
            if "CANCEL" in message or "KEYBOARDINTERRUPT" in message:
                return "cancelled"
            return "terminal"
        if self._contains_any(message, ("RATE_LIMIT", "TOO_MANY_REQUESTS", "429")):
            return "rate_limit"
        if self._contains_any(message, ("TIMEOUT", "TEMPORARY", "UNAVAILABLE", "CONNECTION_RESET", "NETWORK", "SOCKET")):
            return "transport"
        return "unknown"

    def _base_delay(self, *, current_attempt: int, error_family: str) -> int:
        exponent = max(0, current_attempt - 1)
        delay = min(self._max_delay_seconds, self._base_delay_seconds * (2 ** exponent))
        if error_family == "rate_limit":
            return min(self._max_delay_seconds, max(30, delay))
        if error_family == "transport":
            return min(self._max_delay_seconds, max(self._base_delay_seconds, delay))
        return min(self._max_delay_seconds, max(self._base_delay_seconds, delay))

    def classify(self, *, job: JobRecord, error: Exception) -> JobRetryDecision:
        message = f"{type(error).__name__}:{str(error)}".upper()
        error_family = self._error_family(message)
        if error_family in {"authorization", "validation", "cancelled", "terminal"}:
            return JobRetryDecision(False, 0, True, "terminal_error_marker", error_family=error_family)
        current_attempt = int(job.attempts)
        if current_attempt >= int(job.max_attempts):
            return JobRetryDecision(False, 0, True, "attempt_budget_exhausted", error_family=error_family)
        delay = self._base_delay(current_attempt=current_attempt, error_family=error_family)
        if self._jitter_seconds > 0:
            delay += randint(0, self._jitter_seconds)
        return JobRetryDecision(True, int(delay), False, "retryable_failure" if error_family == "unknown" else f"{error_family}_retry", error_family=error_family)


__all__ = [
    "CANON_RUNTIME_QUEUE_RETRY_POLICY",
    "JobRetryDecision",
    "JobRetryPolicy",
]
