from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping

CANON_NON_DECISION_MODULE = True


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    if math.isnan(result) or math.isinf(result):
        return float(default)
    return result


def safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", ""}:
            return False
    return bool(value)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


@dataclass(frozen=True)
class EconomicPolicyConfig:
    currency: str = "RUB"

    min_runway_days: int = 45
    defensive_runway_days: int = 90
    survival_runway_days: int = 45

    liquidity_floor_months: float = 1.0
    required_liquidity_buffer_ratio: float = 0.0

    absolute_floor_margin: float = 0.0
    tolerated_margin_gap: float = 0.03
    default_min_expected_roi: float = 0.0
    negative_roi_veto: bool = True
    max_drawdown_ratio: float = 0.25

    spend_soft_cap_ratio: float = 0.85
    use_planned_spend_as_soft_cap_only: bool = True
    block_negative_roi: bool = True

    allocation_risk_penalty: float = 0.5
    allocation_roi_weight: float = 1.0
    allocation_margin_weight: float = 0.5
    allocation_priority_weight: float = 0.25

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "EconomicPolicyConfig":
        payload = value or {}
        return cls(
            currency=str(payload.get("currency") or "RUB"),
            min_runway_days=max(1, _safe_int(payload.get("min_runway_days", 45), 45)),
            defensive_runway_days=max(1, _safe_int(payload.get("defensive_runway_days", 90), 90)),
            survival_runway_days=max(1, _safe_int(payload.get("survival_runway_days", 45), 45)),
            liquidity_floor_months=max(0.0, safe_float(payload.get("liquidity_floor_months"), 1.0)),
            required_liquidity_buffer_ratio=max(0.0, safe_float(payload.get("required_liquidity_buffer_ratio"), 0.0)),
            absolute_floor_margin=safe_float(payload.get("absolute_floor_margin"), 0.0),
            tolerated_margin_gap=max(0.0, safe_float(payload.get("tolerated_margin_gap"), 0.03)),
            default_min_expected_roi=safe_float(payload.get("default_min_expected_roi"), 0.0),
            negative_roi_veto=safe_bool(payload.get("negative_roi_veto", True), True),
            max_drawdown_ratio=max(0.0, min(1.0, safe_float(payload.get("max_drawdown_ratio"), 0.25))),
            spend_soft_cap_ratio=min(1.0, max(0.0, safe_float(payload.get("spend_soft_cap_ratio"), 0.85))),
            use_planned_spend_as_soft_cap_only=safe_bool(payload.get("use_planned_spend_as_soft_cap_only", True), True),
            block_negative_roi=safe_bool(payload.get("block_negative_roi", True), True),
            allocation_risk_penalty=max(0.0, safe_float(payload.get("allocation_risk_penalty"), 0.5)),
            allocation_roi_weight=max(0.0, safe_float(payload.get("allocation_roi_weight"), 1.0)),
            allocation_margin_weight=max(0.0, safe_float(payload.get("allocation_margin_weight"), 0.5)),
            allocation_priority_weight=max(0.0, safe_float(payload.get("allocation_priority_weight"), 0.25)),
        )


@dataclass(frozen=True)
class PolicyCheckResult:
    policy_name: str
    status: str
    reason: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def is_allow(self) -> bool:
        return self.status == "allow"

    def is_review(self) -> bool:
        return self.status == "review"

    def is_veto(self) -> bool:
        return self.status == "veto"


@dataclass(frozen=True)
class EconomicReviewState:
    allowed: bool
    operator_required: bool
    primary_reason: str
    veto_reasons: tuple[str, ...] = ()
    review_reasons: tuple[str, ...] = ()

    @classmethod
    def from_checks(cls, checks: tuple[PolicyCheckResult, ...]) -> "EconomicReviewState":
        veto_reasons = tuple(check.reason for check in checks if check.is_veto())
        review_reasons = tuple(check.reason for check in checks if check.is_review())
        allowed = len(veto_reasons) == 0
        operator_required = allowed and len(review_reasons) > 0
        if veto_reasons:
            primary_reason = veto_reasons[0]
        elif review_reasons:
            primary_reason = review_reasons[0]
        else:
            primary_reason = "economic_policy_allow"
        return cls(
            allowed=allowed,
            operator_required=operator_required,
            primary_reason=primary_reason,
            veto_reasons=veto_reasons,
            review_reasons=review_reasons,
        )
