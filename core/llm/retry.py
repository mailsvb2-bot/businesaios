from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryConfig:
    """Retry policy.

    Canonical: retry only for transient failures.
    The caller decides which errors are transient.
    """

    max_attempts: int = 3
    base_delay_s: float = 0.4
    max_delay_s: float = 4.0


def default_is_retryable(exc: Exception) -> bool:
    # Best-effort generic classifier.
    # Transport layers may raise RuntimeError with code-like strings.
    msg = str(exc).lower()
    if any(x in msg for x in ("timeout", "tempor", "connection", "network")):
        return True
    if "429" in msg or "rate" in msg:
        return True
    return any(x in msg for x in ("500", "502", "503", "504", "5xx"))


async def with_retry(fn: Callable[[], Awaitable[T]], cfg: RetryConfig, *, is_retryable=default_is_retryable) -> T:
    attempt = 0
    while True:
        attempt += 1
        try:
            return await fn()
        except Exception as e:  # noqa: BLE001
            if attempt >= int(cfg.max_attempts) or not is_retryable(e):
                raise
            delay = min(float(cfg.max_delay_s), float(cfg.base_delay_s) * (2 ** (attempt - 1)))
            delay = delay * (0.7 + 0.6 * random.random())  # jitter
            await asyncio.sleep(delay)
