from __future__ import annotations

from typing import Protocol

from .types import CashflowSummary, LiquiditySnapshot


class NegativeCashflowGuard(Protocol):
    def check(self, summary: CashflowSummary) -> None: ...


class PayoutRiskGuard(Protocol):
    def check(self, payouts, snapshot) -> None: ...


class LiquidityGuard(Protocol):
    def check(self, snapshot: LiquiditySnapshot) -> None: ...
