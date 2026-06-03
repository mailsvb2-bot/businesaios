from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping
from config.risk_evaluation_policy import DEFAULT_ECONOMIC_RISK_ENVELOPE_POLICY


CANON_ECONOMIC_RISK_ENVELOPE = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _text(value: object) -> str:
    return str(value or "").strip()


@dataclass(frozen=True, slots=True)
class EconomicRiskEnvelope:
    risk_level: str
    stress_survival_mode: str
    confidence_floor: float
    downside_roi: float
    upside_roi: float
    approved_budget: float
    requested_budget: float
    requires_operator_review: bool
    reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_level": self.risk_level,
            "stress_survival_mode": self.stress_survival_mode,
            "confidence_floor": float(self.confidence_floor),
            "downside_roi": float(self.downside_roi),
            "upside_roi": float(self.upside_roi),
            "approved_budget": float(self.approved_budget),
            "requested_budget": float(self.requested_budget),
            "requires_operator_review": bool(self.requires_operator_review),
            "reasons": list(self.reasons),
            "metadata": dict(self.metadata),
        }


class EconomicRiskEnvelopeBuilder:
    """
    Read-only risk summarizer.

    Important:
    - Does not decide.
    - Does not veto actions.
    - Only summarizes already computed economic signals into a stable audit shape.
    """

    def build(
        self,
        *,
        planning_signals: Mapping[str, Any] | None,
        spend_limits: Mapping[str, Any] | None = None,
        economic_policy: Mapping[str, Any] | None = None,
    ) -> EconomicRiskEnvelope:
        signals = _safe_dict(planning_signals)
        spend = _safe_dict(spend_limits)
        policy_payload = _safe_dict(economic_policy)
        risk_policy = DEFAULT_ECONOMIC_RISK_ENVELOPE_POLICY
        downside_roi = _safe_float(signals.get("predicted_roi_floor"), default=_safe_float(signals.get("expected_roi")))
        upside_roi = _safe_float(signals.get("predicted_roi_ceiling"), default=_safe_float(signals.get("expected_roi")))
        confidence = max(0.0, min(1.0, _safe_float(signals.get("economic_confidence"), default=1.0)))
        approved_budget = _safe_float(signals.get("approved_budget"), default=_safe_float(spend.get("approved_budget")))
        requested_budget = _safe_float(signals.get("requested_budget"), default=_safe_float(spend.get("requested_budget")))
        requires_operator_review = _safe_bool(signals.get("operator_required")) or _safe_bool(policy_payload.get("operator_required"))
        stress_survival_mode = _text(signals.get("suggested_survival_mode") or signals.get("survival_mode") or policy_payload.get("survival_mode") or "normal")

        reasons: list[str] = []
        if stress_survival_mode == "survival":
            reasons.append("stress_survival_mode")
        if confidence < risk_policy.medium_confidence_threshold:
            reasons.append("low_economic_confidence")
        if downside_roi < risk_policy.medium_downside_threshold:
            reasons.append("negative_downside_roi")
        if approved_budget > 0.0 and requested_budget > approved_budget:
            reasons.append("requested_budget_above_approved_budget")
        if requires_operator_review:
            reasons.append("operator_review_required")

        risk_level = "low"
        if reasons:
            risk_level = "medium"
        if stress_survival_mode == "survival" or downside_roi < risk_policy.high_downside_threshold or confidence < risk_policy.high_confidence_threshold:
            risk_level = "high"
        elif downside_roi < risk_policy.medium_downside_threshold or confidence < risk_policy.medium_confidence_threshold or requires_operator_review:
            risk_level = "medium"

        return EconomicRiskEnvelope(
            risk_level=risk_level,
            stress_survival_mode=stress_survival_mode,
            confidence_floor=confidence,
            downside_roi=downside_roi,
            upside_roi=upside_roi,
            approved_budget=approved_budget,
            requested_budget=requested_budget,
            requires_operator_review=requires_operator_review,
            reasons=tuple(dict.fromkeys(item for item in reasons if _text(item))),
            metadata={
                "owner": "execution.economic_risk_envelope",
            },
        )


__all__ = [
    "CANON_ECONOMIC_RISK_ENVELOPE",
    "EconomicRiskEnvelope",
    "EconomicRiskEnvelopeBuilder",
]
