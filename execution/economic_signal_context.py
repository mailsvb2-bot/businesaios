from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

from execution.channel_roi_memory import ChannelROIMemory
from execution.pre_action_economic_forecast import PreActionEconomicForecastBuilder
from governance.economic.action_economics_model import (
    ActionEconomicsIntent,
    ActionEconomicsSnapshot,
    build_assessment,
)
from governance.economic.economic_policy_contract import EconomicPolicyConfig
from governance.economic.economic_policy_engine import EconomicPolicyEngine

CANON_ECONOMIC_SIGNAL_CONTEXT = True


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
class EconomicPlanningSignals:
    survival_mode: str
    budget_allowed: bool
    operator_required: bool
    expected_roi: float
    runway_days_after_action: float
    approved_budget: float
    requested_budget: float
    channel: str
    action_type: str
    reasons: tuple[str, ...] = ()
    economic_confidence: float = 1.0
    adaptive_expected_roi: float = 0.0
    predicted_roi_floor: float = 0.0
    predicted_roi_ceiling: float = 0.0
    suggested_survival_mode: str = "normal"
    channel_verified_samples: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_decision_context(self) -> dict[str, Any]:
        return {
            "survival_mode": self.survival_mode,
            "budget_allowed": bool(self.budget_allowed),
            "operator_required": bool(self.operator_required),
            "expected_roi": float(self.expected_roi),
            "runway_days_after_action": float(self.runway_days_after_action),
            "approved_budget": float(self.approved_budget),
            "requested_budget": float(self.requested_budget),
            "channel": self.channel,
            "action_type": self.action_type,
            "reasons": list(self.reasons),
            "economic_confidence": float(self.economic_confidence),
            "adaptive_expected_roi": float(self.adaptive_expected_roi),
            "predicted_roi_floor": float(self.predicted_roi_floor),
            "predicted_roi_ceiling": float(self.predicted_roi_ceiling),
            "suggested_survival_mode": self.suggested_survival_mode,
            "channel_verified_samples": int(self.channel_verified_samples),
            "metadata": dict(self.metadata),
        }


class EconomicSignalContextBuilder:
    """
    Read-only decision-context enricher.

    Important:
    - Does not issue decisions.
    - Does not route execution.
    - Prefers already computed economic verdict / budget-guard planning signals.
    - Falls back to policy recomputation only when no canonical computed result exists.
    """

    def __init__(self, *, config: EconomicPolicyConfig | None = None) -> None:
        self._config = config or EconomicPolicyConfig()
        self._channel_roi_memory = ChannelROIMemory()
        self._forecast_builder = PreActionEconomicForecastBuilder()

    def build(
        self,
        *,
        decision_like: Any,
        world_state: Any | None,
        economic_verdict: Any | None = None,
        budget_guard_result: Mapping[str, Any] | None = None,
    ) -> EconomicPlanningSignals:
        precomputed = self._from_budget_guard_result(budget_guard_result)
        if precomputed is not None:
            return precomputed
        if economic_verdict is not None:
            return self._from_economic_verdict(decision_like=decision_like, world_state=world_state, economic_verdict=economic_verdict)
        return self._fallback_recompute(decision_like=decision_like, world_state=world_state)

    def _from_budget_guard_result(self, budget_guard_result: Mapping[str, Any] | None) -> EconomicPlanningSignals | None:
        payload = _safe_dict(budget_guard_result)
        metadata = _safe_dict(payload.get("metadata"))
        planning_signals = _safe_dict(metadata.get("planning_signals"))
        if not planning_signals:
            return None
        return EconomicPlanningSignals(
            survival_mode=_text(planning_signals.get("survival_mode") or "normal"),
            budget_allowed=_safe_bool(planning_signals.get("budget_allowed")),
            operator_required=_safe_bool(planning_signals.get("operator_required")),
            expected_roi=_safe_float(planning_signals.get("expected_roi")),
            runway_days_after_action=_safe_float(planning_signals.get("runway_days_after_action")),
            approved_budget=_safe_float(planning_signals.get("approved_budget")),
            requested_budget=_safe_float(planning_signals.get("requested_budget")),
            channel=_text(planning_signals.get("channel") or "default"),
            action_type=_text(planning_signals.get("action_type") or "unknown"),
            reasons=tuple(str(x) for x in (planning_signals.get("reasons") or ()) if _text(x)),
            economic_confidence=_safe_float(planning_signals.get("economic_confidence"), default=1.0),
            adaptive_expected_roi=_safe_float(planning_signals.get("adaptive_expected_roi"), default=_safe_float(planning_signals.get("expected_roi"))),
            predicted_roi_floor=_safe_float(planning_signals.get("predicted_roi_floor"), default=_safe_float(planning_signals.get("expected_roi"))),
            predicted_roi_ceiling=_safe_float(planning_signals.get("predicted_roi_ceiling"), default=_safe_float(planning_signals.get("expected_roi"))),
            suggested_survival_mode=_text(planning_signals.get("suggested_survival_mode") or planning_signals.get("survival_mode") or "normal"),
            channel_verified_samples=max(0, int(_safe_float(planning_signals.get("channel_verified_samples"), default=0.0))),
            metadata={**_safe_dict(planning_signals.get("metadata")), "owner": "execution.economic_signal_context", "source": "budget_guard_result"},
        )

    def _luxury_fields(self, *, channel: str, action_type: str, world_state: Any | None, expected_roi: float, requested_budget: float, survival_mode: str, runway_days_after_action: float) -> tuple[dict[str, Any], dict[str, Any]]:
        memory = self._channel_roi_memory.from_world_state(world_state=world_state, channel=channel, action_type=action_type)
        forecast = self._forecast_builder.build(
            expected_roi=expected_roi,
            requested_budget=requested_budget,
            current_survival_mode=survival_mode,
            runway_days_after_action=runway_days_after_action,
            memory=memory,
        )
        return memory.to_dict(), forecast.to_dict()

    def _from_economic_verdict(self, *, decision_like: Any, world_state: Any | None, economic_verdict: Any) -> EconomicPlanningSignals:
        intent = ActionEconomicsIntent.from_decision(decision_like, config=self._config)
        assessment = getattr(economic_verdict, "assessment", None)
        verdict_meta = _safe_dict(getattr(economic_verdict, "metadata", {}) or {})
        approved_budget = _safe_float(verdict_meta.get("approved_budget"))
        requested_budget = _safe_float(verdict_meta.get("requested_budget"))
        expected_roi = float(getattr(assessment, "expected_roi", 0.0) if assessment is not None else 0.0)
        runway = float(getattr(assessment, "runway_days_after_action", 0.0) if assessment is not None else 0.0)
        if requested_budget <= 0.0 and assessment is not None:
            requested_budget = float(getattr(assessment, "requested_budget", 0.0) or 0.0)
        channel = _text(intent.channel) or "default"
        action_type = _text(intent.action_type) or "unknown"
        survival_mode = str(getattr(economic_verdict, "survival_mode", "normal") or "normal")
        memory, forecast = self._luxury_fields(
            channel=channel,
            action_type=action_type,
            world_state=world_state,
            expected_roi=expected_roi,
            requested_budget=requested_budget,
            survival_mode=survival_mode,
            runway_days_after_action=runway,
        )
        return EconomicPlanningSignals(
            survival_mode=survival_mode,
            budget_allowed=bool(getattr(economic_verdict, "allowed", False)),
            operator_required=bool(getattr(economic_verdict, "operator_required", False)),
            expected_roi=expected_roi,
            runway_days_after_action=runway,
            approved_budget=approved_budget,
            requested_budget=requested_budget,
            channel=channel,
            action_type=action_type,
            reasons=tuple(str(x) for x in (getattr(economic_verdict, "reasons", ()) or ()) if _text(x)),
            economic_confidence=_safe_float(_safe_dict(forecast.get("confidence")).get("confidence"), default=1.0),
            adaptive_expected_roi=_safe_float(_safe_dict(forecast.get("adaptive_projection")).get("adjusted_expected_roi"), default=expected_roi),
            predicted_roi_floor=_safe_float(_safe_dict(forecast.get("prediction")).get("downside_roi"), default=expected_roi),
            predicted_roi_ceiling=_safe_float(_safe_dict(forecast.get("prediction")).get("upside_roi"), default=expected_roi),
            suggested_survival_mode=_text(_safe_dict(forecast.get("survival_transition")).get("recommended_mode") or survival_mode),
            channel_verified_samples=max(0, int(_safe_float(_safe_dict(memory).get("verified_samples"), default=0.0))),
            metadata={
                "owner": "execution.economic_signal_context",
                "source": "economic_verdict",
                "engine_owner": "governance.economic.economic_policy_engine",
                "luxury_forecast": forecast,
                "channel_roi_memory": memory,
            },
        )

    def _fallback_recompute(self, *, decision_like: Any, world_state: Any | None) -> EconomicPlanningSignals:
        engine = EconomicPolicyEngine(config=self._config)
        intent = ActionEconomicsIntent.from_decision(decision_like, config=self._config)
        snapshot = ActionEconomicsSnapshot.from_sources(decision=decision_like, world_state=world_state, config=self._config)
        assessment = build_assessment(intent, snapshot)
        verdict = engine.review(decision_like, world_state or {})
        verdict_meta = _safe_dict(getattr(verdict, "metadata", {}) or {})
        channel = _text(intent.channel) or "default"
        action_type = _text(intent.action_type) or "unknown"
        survival_mode = str(getattr(verdict, "survival_mode", "normal") or "normal")
        memory, forecast = self._luxury_fields(
            channel=channel,
            action_type=action_type,
            world_state=world_state,
            expected_roi=float(assessment.expected_roi),
            requested_budget=float(assessment.requested_budget),
            survival_mode=survival_mode,
            runway_days_after_action=float(assessment.runway_days_after_action),
        )
        return EconomicPlanningSignals(
            survival_mode=survival_mode,
            budget_allowed=bool(getattr(verdict, "allowed", False)),
            operator_required=bool(getattr(verdict, "operator_required", False)),
            expected_roi=float(assessment.expected_roi),
            runway_days_after_action=float(assessment.runway_days_after_action),
            approved_budget=_safe_float(verdict_meta.get("approved_budget")),
            requested_budget=float(assessment.requested_budget),
            channel=channel,
            action_type=action_type,
            reasons=tuple(str(x) for x in (getattr(verdict, "reasons", ()) or ()) if _text(x)),
            economic_confidence=_safe_float(_safe_dict(forecast.get("confidence")).get("confidence"), default=1.0),
            adaptive_expected_roi=_safe_float(_safe_dict(forecast.get("adaptive_projection")).get("adjusted_expected_roi"), default=float(assessment.expected_roi)),
            predicted_roi_floor=_safe_float(_safe_dict(forecast.get("prediction")).get("downside_roi"), default=float(assessment.expected_roi)),
            predicted_roi_ceiling=_safe_float(_safe_dict(forecast.get("prediction")).get("upside_roi"), default=float(assessment.expected_roi)),
            suggested_survival_mode=_text(_safe_dict(forecast.get("survival_transition")).get("recommended_mode") or survival_mode),
            channel_verified_samples=max(0, int(_safe_float(_safe_dict(memory).get("verified_samples"), default=0.0))),
            metadata={
                "owner": "execution.economic_signal_context",
                "source": "fallback_recompute",
                "engine_owner": "governance.economic.economic_policy_engine",
                "luxury_forecast": forecast,
                "channel_roi_memory": memory,
            },
        )


__all__ = ["CANON_ECONOMIC_SIGNAL_CONTEXT", "EconomicPlanningSignals", "EconomicSignalContextBuilder"]
