from __future__ import annotations

"""Evidence-only behavioral baseline for security signals.

This module learns descriptive baselines only. It must not issue decisions.
"""

import math
from dataclasses import dataclass, field
from typing import Mapping


CANON_SECURITY_BEHAVIORAL_BASELINE = True


@dataclass(frozen=True)
class BaselineSample:
    key: str
    count: int
    mean: float
    variance: float
    minimum: float
    maximum: float

    @property
    def stddev(self) -> float:
        return math.sqrt(max(0.0, self.variance))

    def z_score(self, value: float) -> float:
        if self.count < 2 or self.stddev <= 1e-9:
            return 0.0
        return (float(value) - self.mean) / self.stddev


@dataclass
class BehavioralBaseline:
    _state: dict[str, dict[str, float]] = field(default_factory=dict)

    def observe(self, *, key: str, value: float) -> BaselineSample:
        text = str(key or '').strip()
        if not text:
            raise ValueError('key is required')
        numeric_value = float(value)
        bucket = self._state.setdefault(
            text,
            {
                'count': 0.0,
                'mean': 0.0,
                'm2': 0.0,
                'minimum': numeric_value,
                'maximum': numeric_value,
            },
        )
        bucket['count'] += 1.0
        delta = numeric_value - bucket['mean']
        bucket['mean'] += delta / bucket['count']
        delta2 = numeric_value - bucket['mean']
        bucket['m2'] += delta * delta2
        bucket['minimum'] = min(bucket['minimum'], numeric_value)
        bucket['maximum'] = max(bucket['maximum'], numeric_value)
        return self.snapshot(text)

    def snapshot(self, key: str) -> BaselineSample:
        text = str(key or '').strip()
        if text not in self._state:
            raise KeyError(text)
        bucket = self._state[text]
        count = int(bucket['count'])
        variance = 0.0 if count < 2 else bucket['m2'] / (count - 1)
        return BaselineSample(
            key=text,
            count=count,
            mean=float(bucket['mean']),
            variance=float(variance),
            minimum=float(bucket['minimum']),
            maximum=float(bucket['maximum']),
        )

    def export_state(self) -> Mapping[str, Mapping[str, float]]:
        return {key: dict(value) for key, value in self._state.items()}


__all__ = [
    'BaselineSample',
    'BehavioralBaseline',
    'CANON_SECURITY_BEHAVIORAL_BASELINE',
]
