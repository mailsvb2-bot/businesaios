from __future__ import annotations

from dataclasses import dataclass
import math


CANON_TENANT_BACKEND_RETRY_POLICY = True


@dataclass(frozen=True)
class TenantBackendRetryDecision:
    should_retry: bool
    attempt: int
    delay_seconds: float
    reason: str


@dataclass(frozen=True)
class TenantBackendRetryPolicy:
    max_attempts: int = 4
    base_delay_seconds: float = 0.1
    max_delay_seconds: float = 2.0
    retriable_error_types: tuple[type[BaseException], ...] = (TimeoutError, ConnectionError, OSError)

    def validate(self) -> None:
        if int(self.max_attempts) <= 0:
            raise ValueError('max_attempts must be > 0')
        if float(self.base_delay_seconds) <= 0 or not math.isfinite(float(self.base_delay_seconds)):
            raise ValueError('base_delay_seconds must be finite and > 0')
        if float(self.max_delay_seconds) <= 0 or not math.isfinite(float(self.max_delay_seconds)):
            raise ValueError('max_delay_seconds must be finite and > 0')
        if float(self.max_delay_seconds) < float(self.base_delay_seconds):
            raise ValueError('max_delay_seconds must be >= base_delay_seconds')
        if not self.retriable_error_types:
            raise ValueError('retriable_error_types must not be empty')
        for item in self.retriable_error_types:
            if not isinstance(item, type) or not issubclass(item, BaseException):
                raise TypeError('retriable_error_types must contain exception types')

    def classify(self, *, attempt: int, exc: BaseException) -> TenantBackendRetryDecision:
        self.validate()
        index = int(attempt)
        if index <= 0:
            raise ValueError('attempt must be > 0')
        if not isinstance(exc, BaseException):
            raise TypeError('exc must be an exception instance')
        is_retriable = isinstance(exc, self.retriable_error_types)
        if not is_retriable:
            return TenantBackendRetryDecision(False, index, 0.0, exc.__class__.__name__)
        if index >= int(self.max_attempts):
            return TenantBackendRetryDecision(False, index, 0.0, 'retry_budget_exhausted')
        delay = min(float(self.max_delay_seconds), float(self.base_delay_seconds) * (2 ** (index - 1)))
        return TenantBackendRetryDecision(True, index, delay, exc.__class__.__name__)

    def backoff_schedule(self) -> tuple[float, ...]:
        self.validate()
        result: list[float] = []
        for attempt in range(1, int(self.max_attempts)):
            delay = min(float(self.max_delay_seconds), float(self.base_delay_seconds) * (2 ** (attempt - 1)))
            result.append(delay)
        return tuple(result)

    def retryable_names(self) -> tuple[str, ...]:
        self.validate()
        return tuple(sorted({item.__name__ for item in self.retriable_error_types}))


__all__ = [
    'CANON_TENANT_BACKEND_RETRY_POLICY',
    'TenantBackendRetryDecision',
    'TenantBackendRetryPolicy',
]
