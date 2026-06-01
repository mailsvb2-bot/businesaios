from __future__ import annotations

from dataclasses import dataclass
from time import sleep
from typing import Callable, TypeVar

CANON_RUNTIME_INFERENCE_PROVIDER_RETRY_ADAPTER = True
_T = TypeVar('_T')


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 2
    backoff_seconds: float = 0.0


class ProviderRetryAdapter:
    def __init__(self, policy: RetryPolicy | None = None) -> None:
        self._policy = policy or RetryPolicy()

    def run(self, fn: Callable[[], _T]) -> _T:
        last_error: Exception | None = None
        for attempt in range(max(1, int(self._policy.max_attempts))):
            try:
                return fn()
            except Exception as exc:  # pragma: no cover
                last_error = exc
                if attempt + 1 < self._policy.max_attempts and self._policy.backoff_seconds > 0.0:
                    sleep(self._policy.backoff_seconds)
        assert last_error is not None
        raise last_error
