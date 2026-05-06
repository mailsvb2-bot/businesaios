from __future__ import annotations

from dataclasses import dataclass
from math import atan2, sqrt


@dataclass(frozen=True)
class Complex4:
    re: tuple[float, float, float, float]
    im: tuple[float, float, float, float]

    @classmethod
    def zero(cls) -> "Complex4":
        return cls((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0))

    def add(self, other: "Complex4") -> "Complex4":
        return Complex4(
            tuple(a + b for a, b in zip(self.re, other.re)),
            tuple(a + b for a, b in zip(self.im, other.im)),
        )

    def scale(self, factor: float) -> "Complex4":
        return Complex4(
            tuple(v * factor for v in self.re),
            tuple(v * factor for v in self.im),
        )

    def component_scale(self, factors: tuple[float, float, float, float]) -> "Complex4":
        return Complex4(
            tuple(v * f for v, f in zip(self.re, factors)),
            tuple(v * f for v, f in zip(self.im, factors)),
        )

    def magnitude(self) -> tuple[float, float, float, float]:
        return tuple(sqrt(r * r + i * i) for r, i in zip(self.re, self.im))

    def phase(self) -> tuple[float, float, float, float]:
        return tuple(atan2(i, r) for r, i in zip(self.re, self.im))

    def norm_sq(self) -> float:
        return sum((r * r + i * i) for r, i in zip(self.re, self.im))

    def renormalize(self, ceiling: float = 1.0) -> "Complex4":
        norm = self.norm_sq()
        if norm <= ceiling * ceiling or norm <= 0.0:
            return self
        factor = ceiling / sqrt(norm)
        return self.scale(factor)
