from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2
from core.finance.strategic.types import FinancialInput


class BlendedVsSegmentedCACBuilder:
    def build(self, finance_input: FinancialInput) -> dict:
        total_spend = sum(finance_input.channel_spend.values(), start=Decimal("0"))
        total_customers = sum(finance_input.channel_new_customers.values())
        blended = (total_spend / Decimal(total_customers)) if total_customers else Decimal("0")
        segmented = {
            channel: (
                finance_input.channel_spend.get(channel, Decimal("0")) / Decimal(customers)
                if customers else Decimal("0")
            )
            for channel, customers in finance_input.channel_new_customers.items()
        }
        return {"blended_cac": q2(blended), "segmented_cac": {k: q2(v) for k, v in segmented.items()}}
