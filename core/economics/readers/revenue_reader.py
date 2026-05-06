from __future__ import annotations

from dataclasses import dataclass

from ..types import RevenueSignal


@dataclass
class StaticRevenueReader:
    signal: RevenueSignal

    def read(self) -> RevenueSignal:
        return self.signal
