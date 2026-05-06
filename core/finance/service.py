
from __future__ import annotations

from core.finance.types import FinanceSnapshot, LiquiditySnapshot


def build_liquidity_snapshot(snapshot: FinanceSnapshot) -> LiquiditySnapshot:
    return snapshot.liquidity_snapshot
