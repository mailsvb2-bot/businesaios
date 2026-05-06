from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CircuitBreakerPolicy:
    max_consecutive_failures: int = 3
