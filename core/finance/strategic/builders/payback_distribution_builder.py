from __future__ import annotations

from decimal import Decimal

from config.strategic_finance_simulation_policy import (
    DEFAULT_PAYBACK_DISTRIBUTION_BUILDER_POLICY,
    PaybackDistributionBuilderPolicy,
)
from core.finance.strategic.decimal_utils import q2


class PaybackDistributionBuilder:
    def __init__(self, policy: PaybackDistributionBuilderPolicy = DEFAULT_PAYBACK_DISTRIBUTION_BUILDER_POLICY) -> None:
        self._policy = policy

    def build(self, ltv: Decimal, segmented_cac: dict[str, Decimal]) -> dict[str, Decimal]:
        monthly_value = max(
            ltv / self._policy.months_per_year,
            self._policy.minimum_monthly_value_floor,
        )
        return {channel: q2(cac / monthly_value) for channel, cac in segmented_cac.items()}
