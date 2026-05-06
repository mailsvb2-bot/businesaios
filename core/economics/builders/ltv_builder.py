from __future__ import annotations

from dataclasses import dataclass, field, replace

from config.economics_ltv_policy import DEFAULT_LTV_BUILDER_POLICY, LTVBuilderPolicy

from ..types import CustomerValueSignal, LTVSnapshot


@dataclass
class LTVBuilder:
    default_horizon_months: int | None = None
    policy: LTVBuilderPolicy = field(default_factory=lambda: DEFAULT_LTV_BUILDER_POLICY)

    def __post_init__(self) -> None:
        effective_horizon_months = self.policy.default_horizon_months if self.default_horizon_months is None else self.default_horizon_months
        self.policy = replace(self.policy, default_horizon_months=effective_horizon_months)
        self.default_horizon_months = self.policy.default_horizon_months

    def build(self, customer_value: CustomerValueSignal) -> LTVSnapshot:
        policy = self.policy
        margin_ratio = (
            customer_value.contribution_margin_ratio
            if customer_value.contribution_margin_ratio is not None
            else policy.default_margin_ratio
        )
        if (
            customer_value.average_order_value <= policy.zero_amount
            or customer_value.purchase_frequency_30d <= policy.zero_amount
            or customer_value.gross_retention_30d <= policy.zero_amount
        ):
            return LTVSnapshot(ltv=None, assumptions={"reason": "insufficient_inputs", "margin_ratio": margin_ratio})
        monthly_value = customer_value.average_order_value * customer_value.purchase_frequency_30d * margin_ratio
        retention = min(max(customer_value.gross_retention_30d, policy.minimum_retention), policy.maximum_retention)
        expected_months = min(policy.zero_amount + (1 / (1 - retention)), float(policy.default_horizon_months))
        ltv = monthly_value * expected_months
        return LTVSnapshot(
            ltv=ltv,
            assumptions={
                "margin_ratio": margin_ratio,
                "monthly_value": monthly_value,
                "retention": retention,
                "expected_months": expected_months,
            },
        )
