from __future__ import annotations

from dataclasses import dataclass

from ..types import CashflowSignal


@dataclass
class StaticCashflowReader:
    signal: CashflowSignal

    def read(self) -> CashflowSignal:
        return self.signal
