from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class DebugSampling:
    rate: float = 0.001

    def hit(self) -> bool:
        r = float(self.rate)
        if r <= 0:
            return False
        if r >= 1:
            return True
        return random.random() < r
