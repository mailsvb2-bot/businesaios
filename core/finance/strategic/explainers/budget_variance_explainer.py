from __future__ import annotations

from decimal import Decimal


class BudgetVarianceExplainer:
    def explain(self, budget: Decimal, actual: Decimal) -> str:
        return f'Budget variance is {actual - budget} against budget {budget}.'
