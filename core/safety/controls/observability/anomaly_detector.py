from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from statistics import fmean


CANON_SAFETY_ANOMALY_DETECTOR = True


@dataclass
class SafetyAnomalyDetector:
    history_size: int = 32
    spike_multiplier: float = 2.0
    _history: deque[float] = field(default_factory=deque)

    def record(self, value: float) -> None:
        self._history.append(float(value))
        while len(self._history) > max(3, int(self.history_size)):
            self._history.popleft()

    def detect(self) -> bool:
        if len(self._history) < 5:
            return False
        values = list(self._history)
        baseline = fmean(values[:-1])
        latest = float(values[-1])
        if baseline <= 0.0:
            return latest > 0.0
        return latest >= baseline * max(1.1, float(self.spike_multiplier))


__all__ = ['CANON_SAFETY_ANOMALY_DETECTOR', 'SafetyAnomalyDetector']
