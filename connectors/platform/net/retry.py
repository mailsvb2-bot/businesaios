from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, TypeVar

from interfaces.ads.errors import RateLimitError, TransportError

T = TypeVar("T")

@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay_s: float = 0.5
    max_delay_s: float = 6.0
    jitter: float = 0.2

async def with_retry(fn: Callable[[], Awaitable[T]], *, policy: RetryPolicy) -> T:
    last: Optional[BaseException] = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await fn()
        except RateLimitError as e:
            last = e
            delay = float(e.retry_after_s or 0)
            if delay <= 0:
                delay = _backoff(attempt, policy)
            await asyncio.sleep(delay)
        except TransportError as e:
            last = e
            if e.status is not None and (e.status < 500 and e.status != 429):
                raise
            await asyncio.sleep(_backoff(attempt, policy))
    assert last is not None
    raise last

def _backoff(attempt: int, policy: RetryPolicy) -> float:
    delay = min(policy.max_delay_s, policy.base_delay_s * (2 ** (attempt - 1)))
    delay = delay * (1.0 + (random.random() * 2 - 1) * policy.jitter)
    return max(0.0, delay)
