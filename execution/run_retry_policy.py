from __future__ import annotations

from dataclasses import dataclass, field

from contracts.action_result import ActionResult
from execution.primitives import RetryableStatusSet


@dataclass
class ActionRetry:
    _retryable_statuses: RetryableStatusSet = field(
        default_factory=lambda: RetryableStatusSet(statuses=frozenset({'temporary_failure'}))
    )

    def should_retry(self, result: ActionResult) -> bool:
        return self._retryable_statuses.should_retry(result.status)


__all__ = ['ActionRetry']
