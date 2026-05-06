from __future__ import annotations

from dataclasses import dataclass

from ..types import CashflowSignal, CostSignal, CustomerValueSignal, EconomicsReadModel, RevenueSignal, SpendSignal


@dataclass
class EconomicsReadModelBuilder:
    def build(
        self,
        *,
        revenue: RevenueSignal,
        cost: CostSignal,
        spend: SpendSignal,
        customer_value: CustomerValueSignal,
        cashflow: CashflowSignal,
    ) -> EconomicsReadModel:
        return EconomicsReadModel(
            revenue=revenue,
            cost=cost,
            spend=spend,
            customer_value=customer_value,
            cashflow=cashflow,
        )
