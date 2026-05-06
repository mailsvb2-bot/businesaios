from __future__ import annotations
"""Outbound queue metrics collector.

Tracks latency per priority bucket (wait_ms, exec_ms) in a bounded ring.
Extracted from outbound_queue.py.
"""

import threading
from collections import deque


class OutboundMetricsCollector:
    """Thread-safe collector of (priority, wait_ms, exec_ms) samples."""

    def __init__(self, maxlen: int = 5000) -> None:
        self._lock = threading.Lock()
        self._samples: deque[tuple[int, float, float]] = deque(maxlen=maxlen)

    def record(self, priority: int, wait_ms: float, exec_ms: float) -> None:
        with self._lock:
            self._samples.append((int(priority), float(wait_ms), float(exec_ms)))

    def snapshot(self) -> list[tuple[int, float, float]]:
        with self._lock:
            return list(self._samples)

    @staticmethod
    def _pct(values: list[float], p: float) -> float:
        if not values:
            return 0.0
        sv = sorted(values)
        k = max(0, min(int(round((p / 100.0) * (len(sv) - 1))), len(sv) - 1))
        return float(sv[k])

    def build_snapshot_dict(self, priority_label_fn) -> dict:
        """Return structured snapshot dict keyed by priority label."""
        samples = self.snapshot()

        buckets: dict[str, list[tuple[float, float]]] = {}
        for prio, wait_ms, exec_ms in samples:
            label = priority_label_fn(int(prio))
            buckets.setdefault(label, []).append((float(wait_ms), float(exec_ms)))

        out: dict = {"total_samples": len(samples), "by_priority": {}}
        for label, rows in buckets.items():
            waits = [w for (w, _) in rows]
            execs = [e for (_, e) in rows]
            out["by_priority"][label] = {
                "count": len(rows),
                "wait_ms": {
                    "p50": self._pct(waits, 50),
                    "p95": self._pct(waits, 95),
                    "p99": self._pct(waits, 99),
                },
                "exec_ms": {
                    "p50": self._pct(execs, 50),
                    "p95": self._pct(execs, 95),
                    "p99": self._pct(execs, 99),
                },
            }
        return out
