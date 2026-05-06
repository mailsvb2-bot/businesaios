from __future__ import annotations

from dataclasses import dataclass

from crm.providers.common.crm_http_errors import (
    CrmAuthenticationError,
    CrmHttpError,
    CrmRateLimitError,
    CrmResponseError,
    CrmTimeoutError,
    CrmTransportError,
)


@dataclass(frozen=True)
class CrmRetryDecision:
    should_retry: bool
    delay_seconds: float = 0.0


class CrmRetryPolicy:
    RETRYABLE_CODES = {'429', '500', '502', '503', '504'}

    def __init__(self, *, max_attempts: int = 3, base_delay_seconds: float = 0.25) -> None:
        self.max_attempts = max(max_attempts, 1)
        self.base_delay_seconds = max(base_delay_seconds, 0.0)

    def should_retry(self, status_code: int) -> bool:
        return str(status_code) in self.RETRYABLE_CODES

    def evaluate(self, exc: Exception) -> CrmRetryDecision:
        if not isinstance(exc, CrmHttpError):
            return CrmRetryDecision(False, 0.0)
        attempt = max(exc.context.attempt, 1)
        if attempt >= self.max_attempts:
            return CrmRetryDecision(False, 0.0)
        if isinstance(exc, (CrmTimeoutError, CrmTransportError)):
            return CrmRetryDecision(True, self.base_delay_seconds * attempt)
        if isinstance(exc, CrmRateLimitError):
            retry_after = exc.context.response_headers.get('Retry-After') or exc.context.response_headers.get('retry-after')
            try:
                delay = float(retry_after) if retry_after is not None else self.base_delay_seconds * attempt
            except ValueError:
                delay = self.base_delay_seconds * attempt
            return CrmRetryDecision(True, max(delay, 0.0))
        if isinstance(exc, CrmAuthenticationError):
            return CrmRetryDecision(False, 0.0)
        if isinstance(exc, CrmResponseError) and exc.context.status_code is not None and self.should_retry(exc.context.status_code):
            return CrmRetryDecision(True, self.base_delay_seconds * attempt)
        return CrmRetryDecision(False, 0.0)
