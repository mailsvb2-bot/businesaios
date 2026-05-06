from __future__ import annotations

from dataclasses import dataclass, field

from execution.primitives import RetryableStatusSet


@dataclass(frozen=True)
class RetryPolicy:
    _retryable_statuses: RetryableStatusSet = field(
        default_factory=lambda: RetryableStatusSet(frozenset({'temporary_failure', 'rate_limited'}))
    )

    def should_retry(self, result: dict) -> bool:
        return self._retryable_statuses.should_retry(result.get('status'))
