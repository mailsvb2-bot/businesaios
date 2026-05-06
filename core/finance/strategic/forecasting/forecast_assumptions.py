from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.assumptions.assumption_resolver import AssumptionResolver
from core.finance.strategic.types import FinancialInput


class ForecastAssumptions:
    def __init__(self, resolver: AssumptionResolver | None = None) -> None:
        self._resolver = resolver

    def build(self, finance_input: FinancialInput) -> dict[str, Decimal]:
        explicit = {
            'growth_rate': finance_input.growth_rate,
            'gross_margin_rate': finance_input.gross_margin_rate,
            'churn_rate': finance_input.churn_rate,
            **{key: Decimal(str(value)) for key, value in finance_input.assumptions.items()},
        }
        if self._resolver is None:
            return explicit
        actor = str(finance_input.metadata.get("assumption_actor") or "finance_input")
        return self._resolver.resolve(explicit, actor=actor)
