from __future__ import annotations

from typing import Protocol

from core.finance.strategic.types import FinancialInput


class FinancialInputContract(Protocol):
    def build(self, raw: dict) -> FinancialInput:
        ...
