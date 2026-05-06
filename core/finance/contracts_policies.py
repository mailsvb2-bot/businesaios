from __future__ import annotations

from decimal import Decimal
from typing import Protocol


class ReservePolicy(Protocol):
    def reserve_target(self, average_period_expense: Decimal) -> Decimal: ...


class PayoutPolicy(Protocol):
    def allowed_payout(self, available_cash: Decimal, reserve_target: Decimal) -> Decimal: ...
