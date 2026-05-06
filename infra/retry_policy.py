from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar

from infra.retry_models import RetryPolicySpec


T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    spec: RetryPolicySpec

    def run(self, fn: Callable[[], T]) -> T:
        last_exc: Exception | None = None

        for attempt in range(1, self.spec.max_attempts + 1):
            try:
                return fn()
            except Exception as exc:
                last_exc = exc
                if attempt >= self.spec.max_attempts:
                    break
                if self.spec.delay_seconds > 0:
                    time.sleep(self.spec.delay_seconds)

        assert last_exc is not None
        raise last_exc
