from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CanaryMetrics:
    decisions: int = 0
    errors: int = 0

    @property
    def error_rate(self) -> float:
        return self.errors / self.decisions if self.decisions else 0.0
