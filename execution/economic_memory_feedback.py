from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from execution.cac_learning_engine import CACLearningEngine

CANON_ECONOMIC_MEMORY_FEEDBACK = True


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
class EconomicMemoryFeedbackRecord:
    channel: str
    action_type: str
    expected_roi: float
    approved_budget: float
    requested_budget: float
    realized_revenue: float
    verified: bool
    survival_mode: str
    operator_required: bool
    efficiency_label: str
    memory_key: str
    event_id: str = ''
    estimated_cac: float = 0.0
    payback_hint_months: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_memory_fact(self) -> dict[str, Any]:
        return {
            "kind": "economic_feedback",
            "event_id": self.event_id,
            "memory_key": self.memory_key,
            "channel": self.channel,
            "action_type": self.action_type,
            "expected_roi": float(self.expected_roi),
            "approved_budget": float(self.approved_budget),
            "requested_budget": float(self.requested_budget),
            "realized_revenue": float(self.realized_revenue),
            "verified": bool(self.verified),
            "survival_mode": self.survival_mode,
            "operator_required": bool(self.operator_required),
            "efficiency_label": self.efficiency_label,
            "estimated_cac": float(self.estimated_cac),
            "payback_hint_months": float(self.payback_hint_months),
            "metadata": dict(self.metadata),
        }


class EconomicMemoryFeedback:
    """
    Normalizes economic outcomes into canonical business-memory facts.

    Important:
    - Does not decide.
    - Does not plan.
    - Emits compact factual feedback only.
    - Does not create a parallel memory brain.
    """

    def __init__(self, *, cac_learning_engine: CACLearningEngine | None = None) -> None:
        self._cac_learning_engine = cac_learning_engine or CACLearningEngine()

    def build(
        self,
        *,
        action_type: str,
        event_id: str = '',
        budget_guard_result: Mapping[str, Any] | None = None,
        planning_signals: Mapping[str, Any] | None = None,
        revenue_verification_result: Mapping[str, Any] | None = None,
    ) -> EconomicMemoryFeedbackRecord:
        budget_payload = _safe_dict(budget_guard_result)
        signals_payload = self._resolve_signals(budget_guard_result=budget_payload, planning_signals=planning_signals)
        revenue_payload = _safe_dict(revenue_verification_result)

        expected_roi = _safe_float(signals_payload.get("expected_roi"))
        approved_budget = _safe_float(signals_payload.get("approved_budget"))
        requested_budget = _safe_float(signals_payload.get("requested_budget"))
        realized_revenue = _safe_float(revenue_payload.get("revenue_amount"))
        verified = _safe_bool(revenue_payload.get("verified"))
        survival_mode = _text(signals_payload.get("suggested_survival_mode") or signals_payload.get("survival_mode") or "normal")
        operator_required = _safe_bool(signals_payload.get("operator_required"))
        channel = _text(signals_payload.get("channel") or _safe_dict(budget_payload.get("metadata")).get("channel") or "default")
        normalized_action_type = _text(action_type) or _text(signals_payload.get("action_type")) or _text(_safe_dict(budget_payload.get("metadata")).get("action_type")) or "unknown"
        cac_snapshot = self._cac_learning_engine.estimate(budget_guard_result=budget_payload, revenue_verification_result=revenue_payload)

        efficiency_label = self._efficiency_label(
            expected_roi=expected_roi,
            realized_revenue=realized_revenue,
            verified=verified,
            survival_mode=survival_mode,
            operator_required=operator_required,
        )
        memory_key = f"economic::{channel}::{normalized_action_type}::{efficiency_label}"

        return EconomicMemoryFeedbackRecord(
            event_id=_text(event_id),
            channel=channel,
            action_type=normalized_action_type,
            expected_roi=expected_roi,
            approved_budget=approved_budget,
            requested_budget=requested_budget,
            realized_revenue=realized_revenue,
            verified=verified,
            survival_mode=survival_mode,
            operator_required=operator_required,
            efficiency_label=efficiency_label,
            memory_key=memory_key,
            estimated_cac=float(cac_snapshot.estimated_cac),
            payback_hint_months=float(cac_snapshot.payback_hint_months),
            metadata={
                "owner": "execution.economic_memory_feedback",
                "cac_snapshot": cac_snapshot.to_dict(),
                "economic_confidence": _safe_float(signals_payload.get("economic_confidence"), default=1.0),
                "adaptive_expected_roi": _safe_float(signals_payload.get("adaptive_expected_roi"), default=expected_roi),
            },
        )

    @staticmethod
    def _resolve_signals(*, budget_guard_result: Mapping[str, Any], planning_signals: Mapping[str, Any] | None) -> dict[str, Any]:
        direct = _safe_dict(planning_signals)
        if direct:
            return direct
        metadata = _safe_dict(budget_guard_result.get("metadata"))
        nested = _safe_dict(metadata.get("planning_signals"))
        if nested:
            return nested
        spend_limits = _safe_dict(budget_guard_result.get("spend_limits"))
        assessment = _safe_dict(spend_limits.get("assessment"))
        economic_policy = _safe_dict(budget_guard_result.get("economic_policy"))
        return {
            "expected_roi": assessment.get("expected_roi"),
            "approved_budget": spend_limits.get("approved_budget"),
            "requested_budget": spend_limits.get("requested_budget"),
            "survival_mode": economic_policy.get("survival_mode"),
            "operator_required": budget_guard_result.get("operator_required"),
            "channel": metadata.get("channel"),
            "action_type": metadata.get("action_type"),
            "economic_confidence": metadata.get("economic_confidence"),
            "suggested_survival_mode": metadata.get("suggested_survival_mode"),
        }

    @staticmethod
    def _efficiency_label(*, expected_roi: float, realized_revenue: float, verified: bool, survival_mode: str, operator_required: bool) -> str:
        if not verified:
            return "unverified"
        if operator_required:
            return "verified_operator_reviewed"
        if survival_mode == "survival":
            return "survival_guarded"
        if realized_revenue <= 0.0:
            return "verified_no_revenue"
        if expected_roi < 0.0:
            return "verified_negative_roi"
        if expected_roi < 0.25:
            return "verified_low_roi"
        return "verified_positive_roi"


__all__ = ["CANON_ECONOMIC_MEMORY_FEEDBACK", "EconomicMemoryFeedback", "EconomicMemoryFeedbackRecord"]
