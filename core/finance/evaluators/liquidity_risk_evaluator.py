from __future__ import annotations

from decimal import Decimal

from config.risk_evaluation_policy import (
    DEFAULT_LIQUIDITY_RISK_POLICY,
    LiquidityRiskPolicy,
)
from core.finance.types import LiquiditySnapshot


def evaluate_liquidity_risk(
    snapshot: LiquiditySnapshot,
    *,
    policy: LiquidityRiskPolicy = DEFAULT_LIQUIDITY_RISK_POLICY,
) -> float:
    if snapshot.available_cash < 0:
        return float(policy.negative_cash_risk)
    if snapshot.reserve_target <= 0:
        return float(policy.no_reserve_target_risk)
    ratio = Decimal(snapshot.available_cash) / Decimal(snapshot.reserve_target)
    if ratio < Decimal(str(policy.severe_ratio_threshold)):
        return float(policy.severe_ratio_risk)
    if ratio < Decimal(str(policy.warning_ratio_threshold)):
        return float(policy.warning_ratio_risk)
    return float(policy.healthy_ratio_risk)
