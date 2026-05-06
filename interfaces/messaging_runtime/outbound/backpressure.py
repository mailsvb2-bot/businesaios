from __future__ import annotations


class BackpressureViolation(RuntimeError):
    pass


class QueueBackpressureGuard:
    def __init__(self, max_size: int) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be > 0")
        self._max_size = max_size

    def check(self, current_size: int) -> None:
        if current_size >= self._max_size:
            raise BackpressureViolation(f"outbound queue limit reached: {current_size} >= {self._max_size}")
