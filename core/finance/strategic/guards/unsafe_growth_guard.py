from __future__ import annotations

from decimal import Decimal

from config.strategic_finance_simulation_policy import (
    DEFAULT_UNSAFE_GROWTH_GUARD_POLICY,
    UnsafeGrowthGuardPolicy,
)
from core.finance.strategic.types import GuardResult


class UnsafeGrowthGuard:
    def __init__(self, policy: UnsafeGrowthGuardPolicy = DEFAULT_UNSAFE_GROWTH_GUARD_POLICY) -> None:
        self._policy = policy

    def check(
        self,
        growth_rate: Decimal,
        gross_margin_rate: Decimal,
        max_growth: Decimal | None = None,
        min_margin: Decimal | None = None,
    ) -> GuardResult:
        growth_limit = self._policy.max_growth if max_growth is None else max_growth
        margin_floor = self._policy.minimum_margin if min_margin is None else min_margin
        ok = not (growth_rate > growth_limit and gross_margin_rate < margin_floor)
        return GuardResult(ok=ok, code='unsafe_growth', message='Unsafe growth check completed.')
