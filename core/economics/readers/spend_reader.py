from __future__ import annotations

from dataclasses import dataclass

from ..types import SpendSignal


@dataclass
class StaticSpendReader:
    signal: SpendSignal

    def read(self) -> SpendSignal:
        return self.signal
