from __future__ import annotations

"""Small deterministic complex vector used by Behavioral OS.

Complex numbers are represented as separate real/imag tuples for speed
and deterministic serialization.
"""

import math
from dataclasses import dataclass

EPS = 1e-9


@dataclass(frozen=True)
class Complex4:
    re: tuple[float, float, float, float]
    im: tuple[float, float, float, float]

    @staticmethod
    def zeros() -> Complex4:
        return Complex4((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0))

    def norm2(self) -> float:
        return float(sum((a * a + b * b) for a, b in zip(self.re, self.im, strict=False)))

    def renormalize(self, target_norm: float = 1.0) -> Complex4:
        n2 = self.norm2()
        if n2 <= EPS:
            # Zero-norm state: choose a deterministic unit basis to keep invariants.
            return Complex4((1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0))
        s = math.sqrt(float(target_norm) / float(n2))
        return Complex4(tuple(float(x * s) for x in self.re), tuple(float(x * s) for x in self.im))

    def phases(self) -> tuple[float, float, float, float]:
        out = []
        for a, b in zip(self.re, self.im, strict=False):
            if abs(a) <= EPS and abs(b) <= EPS:
                out.append(0.0)
            else:
                out.append(float(math.atan2(b, a)))
        return tuple(out)  # type: ignore[return-value]
