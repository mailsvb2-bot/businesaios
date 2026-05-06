from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

CANON_PROVIDER_RETRY_POLICY = True


@dataclass(frozen=True)
class ProviderRetryDecision:
    provider_key: str
    category: str
    retryable: bool
    next_delay_seconds: int
    max_attempts: int
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ProviderRetryPolicy:
    def evaluate(self, *, provider_key: str, category: str, retryable: bool, attempt: int = 1) -> ProviderRetryDecision:
        normalized_attempt = max(1, int(attempt or 1))
        normalized_category = str(category or 'provider_runtime_error').strip() or 'provider_runtime_error'
        if not retryable:
            return ProviderRetryDecision(provider_key=provider_key, category=normalized_category, retryable=False, next_delay_seconds=0, max_attempts=1, metadata={'attempt': normalized_attempt, 'policy': 'fail_closed'})
        if normalized_category == 'transport_timeout':
            base = 15
            max_attempts = 5
        elif normalized_category == 'transport_unavailable':
            base = 30
            max_attempts = 6
        else:
            base = 20
            max_attempts = 3
        next_delay = min(base * (2 ** max(0, normalized_attempt - 1)), 900)
        return ProviderRetryDecision(provider_key=provider_key, category=normalized_category, retryable=True, next_delay_seconds=next_delay, max_attempts=max_attempts, metadata={'attempt': normalized_attempt, 'policy': 'exponential_backoff'})
    decide = evaluate


__all__ = ['CANON_PROVIDER_RETRY_POLICY', 'ProviderRetryDecision', 'ProviderRetryPolicy']
