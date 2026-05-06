from __future__ import annotations

from dataclasses import dataclass

from ..types import CACSnapshot, CustomerValueSignal, SpendSignal


@dataclass
class CACBuilder:
    def build(self, *, spend: SpendSignal, customer_value: CustomerValueSignal) -> CACSnapshot:
        attributed_new_customers = max(customer_value.new_customers, 0)
        if attributed_new_customers <= 0:
            return CACSnapshot(blended_cac=None, attributed_new_customers=0)
        acquisition_spend = spend.marketing_spend + spend.sales_spend
        return CACSnapshot(
            blended_cac=acquisition_spend / attributed_new_customers,
            attributed_new_customers=attributed_new_customers,
        )
