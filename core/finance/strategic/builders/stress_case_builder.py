from __future__ import annotations

from config.strategic_finance_simulation_policy import (
    DEFAULT_STRESS_CASE_BUILDER_POLICY,
    StressCaseBuilderPolicy,
)
from core.finance.strategic.types import Scenario


class StressCaseBuilder:
    def __init__(self, policy: StressCaseBuilderPolicy = DEFAULT_STRESS_CASE_BUILDER_POLICY) -> None:
        self._policy = policy

    def build(self) -> Scenario:
        return Scenario(
            name=self._policy.name,
            revenue_multiplier=self._policy.revenue_multiplier,
            cost_multiplier=self._policy.cost_multiplier,
            probability=self._policy.probability,
            notes=self._policy.notes,
        )
