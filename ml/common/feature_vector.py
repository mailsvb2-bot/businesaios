from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Mapping

from shared.numbers import coerce_float


@dataclass(frozen=True)
class FeatureVector:
    values: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object] | None) -> 'FeatureVector':
        values: Dict[str, float] = {}
        if payload is None:
            return cls(values=values)
        for key, value in payload.items():
            if isinstance(value, bool):
                values[str(key)] = 1.0 if value else 0.0
                continue
            if not isinstance(value, (int, float)):
                continue
            if not math.isfinite(float(value)):
                continue
            values[str(key)] = coerce_float(value, 0.0)
        return cls(values=values)

    def merge(self, payload: Mapping[str, object]) -> 'FeatureVector':
        merged = dict(self.values)
        merged.update(self.from_mapping(payload).values)
        return FeatureVector(values=merged)
