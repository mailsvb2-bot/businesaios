from __future__ import annotations

import math
from collections.abc import Sequence


class ConvergencePolicy:
    def converged(
        self,
        scores: Sequence[float],
        tolerance: float = 1e-3,
        *,
        window: int = 3,
        min_samples: int = 3,
    ) -> bool:
        if min_samples < 2:
            min_samples = 2
        if window < 2:
            window = 2
        if len(scores) < max(min_samples, window):
            return False

        recent = [float(value) for value in scores[-window:]]
        if not all(math.isfinite(value) for value in recent):
            return False

        spread = max(recent) - min(recent)
        return spread <= abs(float(tolerance))

__all__ = [
    "ConvergencePolicy",
]
