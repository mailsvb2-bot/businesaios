"""Clock abstraction.

Ring invariants depend on determinism. Any use of wall-clock time in the
decision/verification pipeline must be routed through a clock object.
"""

from __future__ import annotations

import time

class Clock:
    def now_ms(self) -> int:
        raise NotImplementedError


class SystemClock(Clock):
    def now_ms(self) -> int:
        return int(time.time() * 1000)


class MonotonicClock(Clock):
    """Monotonic source for duration/replay windows.

    Keeps runtime code from mixing wall-clock timestamps with latency measurement.
    """

    def now_ms(self) -> int:
        return int(time.monotonic() * 1000)


class DeterministicClock(Clock):
    """Deterministic clock for tests/replay."""

    def __init__(self, start_ms: int):
        self._now = int(start_ms)

    def now_ms(self) -> int:
        return int(self._now)

    def advance_ms(self, delta_ms: int) -> None:
        self._now += int(delta_ms)
