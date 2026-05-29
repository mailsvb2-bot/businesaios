from __future__ import annotations

from dataclasses import dataclass

from config.economics_core_policy import DEFAULT_ECONOMICS_CORE_POLICY, EconomicsCorePolicy


@dataclass(frozen=True)
class EconomicsConfigV1:
    """Economics (marketing) configuration.

    IMPORTANT ARCHITECTURE:
    - CAC lives here (economics layer), not inside offers/pricing engines.
    - Product pricing ladder lives in product layer.
    - DecisionCore is the single point that turns economics+state into constraints.
    """

    # Marketing economics (not product price)
    target_cac_rub: int = DEFAULT_ECONOMICS_CORE_POLICY.target_cac_rub

    # Payback target: rough guardrail for aggressiveness
    target_payback_days: int = DEFAULT_ECONOMICS_CORE_POLICY.target_payback_days

    # Safety ratio: require LTV >= CAC * ratio to go "standard/premium"
    min_ltv_cac_ratio: float = DEFAULT_ECONOMICS_CORE_POLICY.min_ltv_cac_ratio

    @staticmethod
    def from_dict(d: dict | None, *, policy: EconomicsCorePolicy | None = None) -> EconomicsConfigV1:
        d = d or {}
        policy = policy or DEFAULT_ECONOMICS_CORE_POLICY
        return EconomicsConfigV1(
            target_cac_rub=int(d.get("target_cac_rub", int(policy.target_cac_rub))),
            target_payback_days=int(d.get("target_payback_days", int(policy.target_payback_days))),
            min_ltv_cac_ratio=float(d.get("min_ltv_cac_ratio", float(policy.min_ltv_cac_ratio))),
        )
