from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class Stopwatch:
    started_at: float
    finished_at: float | None = None

    @property
    def duration_ms(self) -> int:
        end = self.finished_at if self.finished_at is not None else time.perf_counter()
        return int((end - self.started_at) * 1000)


@contextmanager
def measure_time() -> Iterator[Stopwatch]:
    watch = Stopwatch(started_at=time.perf_counter())
    try:
        yield watch
    finally:
        watch.finished_at = time.perf_counter()
