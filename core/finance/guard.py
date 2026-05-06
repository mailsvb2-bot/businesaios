
from __future__ import annotations

from core.finance.errors import FinanceGuardViolation
from core.finance.types import LiquiditySnapshot


def require_non_negative_liquidity(snapshot: LiquiditySnapshot) -> None:
    if snapshot.available_cash < 0:
        raise FinanceGuardViolation('Available cash must not be negative.')
