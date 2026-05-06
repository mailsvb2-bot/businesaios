from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class MetricSnapshot:
    ts_ms: int
    counters: Dict[str, int]
    latencies_ms: List[int]
    tokens_total: int


class LLMMetrics:
    """Lightweight in-memory metrics (no new infra)."""

    def __init__(self, *, keep_last: int = 200) -> None:
        self._c: Dict[str, int] = {}
        self._lat: List[int] = []
        self._tokens_total: int = 0
        self._keep_last = int(keep_last)

    def inc(self, name: str, n: int = 1) -> None:
        self._c[str(name)] = int(self._c.get(str(name), 0)) + int(n)

    def observe_latency(self, ms: int) -> None:
        self._lat.append(int(ms))
        if len(self._lat) > self._keep_last:
            self._lat = self._lat[-self._keep_last :]

    def add_tokens(self, n: int) -> None:
        self._tokens_total += int(n)

    def snapshot(self) -> MetricSnapshot:
        return MetricSnapshot(
            ts_ms=int(time.time() * 1000),
            counters=dict(self._c),
            latencies_ms=list(self._lat),
            tokens_total=int(self._tokens_total),
        )

    def p95_latency(self) -> int:
        if not self._lat:
            return 0
        s = sorted(self._lat)
        idx = int(0.95 * (len(s) - 1))
        return int(s[idx])
