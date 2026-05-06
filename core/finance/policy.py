
from __future__ import annotations

from decimal import Decimal

from core.finance.types import LiquiditySnapshot, ReservePolicyResult


def build_reserve_policy_result(snapshot: LiquiditySnapshot) -> ReservePolicyResult:
    reserve_amount = snapshot.available_cash * Decimal('0.2') if snapshot.available_cash > 0 else Decimal('0')
    return ReservePolicyResult(keep_reserve=reserve_amount > 0, reserve_amount=reserve_amount)
