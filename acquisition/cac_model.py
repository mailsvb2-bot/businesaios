from __future__ import annotations

from dataclasses import dataclass

from shared.numbers import coerce_float, coerce_int

CANON_ACQUISITION_CAC_MODEL = True


@dataclass(frozen=True, slots=True)
class CacInputs:
    total_budget: float
    acquired_customers: int
    gross_margin_ltv: float
    max_cac_to_ltv_ratio: float = 0.33
    payback_horizon_months: float = 12.0
    expected_monthly_margin_per_customer: float = 0.0
    setup_cost: float = 0.0


@dataclass(frozen=True, slots=True)
class CacSnapshot:
    blended_cac: float
    variable_cac: float
    setup_cost_share: float
    gross_margin_ltv: float
    max_sustainable_cac: float
    ltv_to_cac_ratio: float
    payback_months: float
    sustainable: bool
    reasons: tuple[str, ...]


class CustomerAcquisitionCostModel:
    def evaluate(self, inputs: CacInputs) -> CacSnapshot:
        total_budget = coerce_float(inputs.total_budget, 0.0, minimum=0.0)
        acquired_customers = coerce_int(inputs.acquired_customers, 0, minimum=0)
        gross_margin_ltv = coerce_float(inputs.gross_margin_ltv, 0.0, minimum=0.0)
        max_cac_to_ltv_ratio = coerce_float(inputs.max_cac_to_ltv_ratio, 0.33, minimum=0.0)
        payback_horizon_months = coerce_float(inputs.payback_horizon_months, 12.0, minimum=0.0)
        expected_monthly_margin_per_customer = coerce_float(inputs.expected_monthly_margin_per_customer, 0.0, minimum=0.0)
        setup_cost = coerce_float(inputs.setup_cost, 0.0, minimum=0.0)

        if acquired_customers <= 0:
            reasons_list = ["no_acquired_customers"]
            if gross_margin_ltv <= 0.0:
                reasons_list.append("no_gross_margin_ltv")
            return CacSnapshot(
                blended_cac=0.0,
                variable_cac=0.0,
                setup_cost_share=0.0,
                gross_margin_ltv=gross_margin_ltv,
                max_sustainable_cac=round(gross_margin_ltv * max_cac_to_ltv_ratio, 4),
                ltv_to_cac_ratio=0.0,
                payback_months=payback_horizon_months,
                sustainable=False,
                reasons=tuple(reasons_list),
            )

        setup_cost_share = setup_cost / acquired_customers
        variable_cac = max(0.0, (total_budget - setup_cost) / acquired_customers)
        blended_cac = total_budget / acquired_customers
        max_sustainable_cac = gross_margin_ltv * max_cac_to_ltv_ratio
        ltv_to_cac_ratio = gross_margin_ltv / blended_cac if blended_cac > 0.0 else 0.0
        payback_months = blended_cac / expected_monthly_margin_per_customer if expected_monthly_margin_per_customer > 0.0 else payback_horizon_months

        reasons: list[str] = []
        sustainable = True
        if gross_margin_ltv <= 0.0:
            sustainable = False
            reasons.append("no_gross_margin_ltv")
        if blended_cac > max_sustainable_cac and max_sustainable_cac > 0.0:
            sustainable = False
            reasons.append("cac_above_sustainable_threshold")
        if expected_monthly_margin_per_customer <= 0.0:
            sustainable = False
            reasons.append("no_monthly_margin_signal")
        elif payback_months > payback_horizon_months:
            sustainable = False
            reasons.append("payback_too_slow")

        return CacSnapshot(
            blended_cac=round(blended_cac, 4),
            variable_cac=round(variable_cac, 4),
            setup_cost_share=round(setup_cost_share, 4),
            gross_margin_ltv=round(gross_margin_ltv, 4),
            max_sustainable_cac=round(max_sustainable_cac, 4),
            ltv_to_cac_ratio=round(ltv_to_cac_ratio, 4),
            payback_months=round(payback_months, 4),
            sustainable=sustainable,
            reasons=tuple(reasons),
        )
