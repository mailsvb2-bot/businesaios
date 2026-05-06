from __future__ import annotations

from dataclasses import dataclass, field


CANON_MARKET_INTELLIGENCE_RETRY_POLICY = True


@dataclass(frozen=True)
class MarketIntelligenceRetryPolicy:
    max_attempts: int = 3
    base_backoff_seconds: float = 0.05
    retryable_codes: tuple[str, ...] = field(default_factory=lambda: (
        'timeout',
        'throttled',
        'temporary_unavailable',
        'temporarily_unavailable',
        'network_error',
        'provider_error',
    ))

    def should_retry(self, *, attempt: int, code: str | None) -> bool:
        normalized_code = str(code or '').strip().lower()
        return attempt < int(self.max_attempts) and normalized_code in set(self.retryable_codes)

    def backoff_seconds(self, attempt: int) -> float:
        bounded = max(1, int(attempt))
        return min(float(self.base_backoff_seconds) * (2 ** (bounded - 1)), 1.0)


__all__ = ['CANON_MARKET_INTELLIGENCE_RETRY_POLICY', 'MarketIntelligenceRetryPolicy']
