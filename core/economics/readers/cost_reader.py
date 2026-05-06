from __future__ import annotations

from dataclasses import dataclass

from ..types import CostSignal


@dataclass
class StaticCostReader:
    signal: CostSignal

    def read(self) -> CostSignal:
        return self.signal
