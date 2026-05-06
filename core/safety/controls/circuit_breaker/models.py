from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CircuitBreakerState:
    key: str
    consecutive_failures: int = 0
    opened: bool = False
