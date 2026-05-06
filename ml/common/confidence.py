from __future__ import annotations

from dataclasses import dataclass

from shared.numbers import coerce_float


@dataclass(frozen=True)
class Confidence:
    value: float

    def bounded(self) -> float:
        return coerce_float(self.value, 0.0, minimum=0.0, maximum=1.0)
