from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

from interfaces.ads.errors import RateLimitError, TransportError

T = TypeVar("T")

@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay_s: float = 0.5
    max_delay_s: float = 6.0
    jitter: float = 0.2
    max_retry_after_s: float = 60.0

async def with_retry(fn: Callable[[], Awaitable[T]], *, policy: RetryPolicy) -> T:
    attempts = max(1, int(policy.max_attempts))
    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except RateLimitError as exc:
            if attempt == attempts:
                raise
            retry_after = float(exc.retry_after_s or 0)
            delay = retry_after if retry_after > 0 else _backoff(attempt, policy)
            await asyncio.sleep(min(delay, max(0.0, policy.max_retry_after_s)))
        except TransportError as exc:
            if exc.status is not None and exc.status < 500 and exc.status != 429:
                raise
            if attempt == attempts:
                raise
            await asyncio.sleep(_backoff(attempt, policy))
    raise AssertionError('unreachable')

def _backoff(attempt: int, policy: RetryPolicy) -> float:
    delay = min(policy.max_delay_s, policy.base_delay_s * (2 ** (attempt - 1)))
    delay = delay * (1.0 + (random.random() * 2 - 1) * policy.jitter)
    return max(0.0, delay)
