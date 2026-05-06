from __future__ import annotations

from dataclasses import dataclass

from ..errors import EconomicsDataError
from ..types import CashflowSignal, CostSignal, CustomerValueSignal, RevenueSignal, SpendSignal


@dataclass
class EconomicsSignalValidator:
    def validate(
        self,
        *,
        revenue: RevenueSignal,
        cost: CostSignal,
        spend: SpendSignal,
        customer_value: CustomerValueSignal,
        cashflow: CashflowSignal,
    ) -> None:
        for field_name, value in {
            "revenue.period_days": revenue.period_days,
            "cost.period_days": cost.period_days,
            "spend.period_days": spend.period_days,
        }.items():
            if value <= 0:
                raise EconomicsDataError(f"{field_name} must be > 0")
        for field_name, value in {
            "revenue.gross_revenue": revenue.gross_revenue,
            "revenue.net_revenue": revenue.net_revenue,
            "revenue.orders": revenue.orders,
            "cost.cogs": cost.cogs,
            "cost.fixed_costs": cost.fixed_costs,
            "cost.variable_costs": cost.variable_costs,
            "spend.marketing_spend": spend.marketing_spend,
            "spend.sales_spend": spend.sales_spend,
            "spend.operations_spend": spend.operations_spend,
            "customer_value.active_customers": customer_value.active_customers,
            "customer_value.new_customers": customer_value.new_customers,
            "customer_value.returning_customers": customer_value.returning_customers,
            "customer_value.average_order_value": customer_value.average_order_value,
            "customer_value.purchase_frequency_30d": customer_value.purchase_frequency_30d,
            "cashflow.cash_in": cashflow.cash_in,
            "cashflow.cash_out": cashflow.cash_out,
            "cashflow.unrestricted_cash": cashflow.unrestricted_cash,
        }.items():
            if value < 0:
                raise EconomicsDataError(f"{field_name} must be >= 0")
        if not 0 <= customer_value.gross_retention_30d <= 1:
            raise EconomicsDataError("customer_value.gross_retention_30d must be between 0 and 1")
        if customer_value.new_customers > customer_value.active_customers:
            raise EconomicsDataError("customer_value.new_customers cannot exceed active_customers")
        if cashflow.runway_days is not None and cashflow.runway_days < 0:
            raise EconomicsDataError("cashflow.runway_days must be >= 0")
