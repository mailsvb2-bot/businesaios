from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass, field
from typing import Dict

from shared.numbers import coerce_float


@dataclass
class MetricCounter:
    values: Dict[str, float] = field(default_factory=dict)

    def observe(self, name: str, value: float = 1.0) -> None:
        key = str(name).strip()
        if not key:
            raise ValueError('metric name must be non-empty')
        numeric = coerce_float(value, 0.0)
        self.values[key] = self.values.get(key, 0.0) + numeric

    def inc(self, name: str, value: float = 1.0) -> None:
        self.observe(name, value)

    def snapshot(self) -> Dict[str, float]:
        return dict(self.values)
