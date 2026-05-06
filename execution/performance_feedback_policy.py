from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from execution.budget_posture_contract import BudgetPostureRecommendation


CANON_PERFORMANCE_FEEDBACK_POLICY = True


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _text(value: object) -> str:
    return str(value or '').strip()


def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0.0:
        return 0.0
    return max(0.0, min(1.0, numerator / denominator))


@dataclass(frozen=True)
class PerformanceFeedbackPolicyView:
    execution_success_rate: float
    verification_rate: float
    goal_achievement_rate: float
    cost_efficiency_score: float
    budget_posture: BudgetPostureRecommendation
    recent_signals: tuple[str, ...]


class PerformanceFeedbackPolicy:
    def classify_budget_posture(self, *, verification_rate: float, achievement_rate: float, cost_efficiency_score: float) -> BudgetPostureRecommendation:
        reasons: list[str] = []
        posture = 'neutral'
        cost_multiplier = 1.0
        total_multiplier = 1.0
        confidence = max(verification_rate, achievement_rate, cost_efficiency_score)
        if verification_rate >= 0.70 and achievement_rate >= 0.55 and cost_efficiency_score >= 0.55:
            posture = 'expand_carefully'
            cost_multiplier = 1.10
            total_multiplier = 1.08
            reasons.append('verified_and_efficient')
        elif verification_rate < 0.35 or (cost_efficiency_score < 0.25 and achievement_rate < 0.25 and verification_rate < 0.60):
            posture = 'tighten'
            cost_multiplier = 0.85
            total_multiplier = 0.90
            reasons.append('weak_verification_or_efficiency')
        else:
            reasons.append('mixed_or_insufficient_signal')
        if achievement_rate < 0.30:
            reasons.append('low_goal_achievement')
        if verification_rate >= 0.80:
            reasons.append('high_verification')
        return BudgetPostureRecommendation(
            posture=posture,
            cost_multiplier=cost_multiplier,
            total_budget_multiplier=total_multiplier,
            outbound_multiplier=1.0 if posture != 'tighten' else 0.90,
            publication_multiplier=1.0 if posture != 'tighten' else 0.90,
            confidence=max(0.0, min(1.0, confidence)),
            reasons=tuple(reasons),
        )

    def build_view(self, *, counters: Mapping[str, Any], spent_total: float) -> PerformanceFeedbackPolicyView:
        total = max(0.0, _safe_float(counters.get('total_steps')))
        executed = max(0.0, _safe_float(counters.get('executed_steps')))
        verified = max(0.0, _safe_float(counters.get('verified_steps')))
        achieved = max(0.0, _safe_float(counters.get('achieved_steps')))
        execution_success_rate = _ratio(executed, total)
        verification_rate = _ratio(verified, executed)
        goal_achievement_rate = _ratio(achieved, total)
        cost_efficiency_score = max(0.0, min(1.0, goal_achievement_rate / max(0.25, spent_total))) if spent_total > 0 else goal_achievement_rate
        budget_posture = self.classify_budget_posture(
            verification_rate=verification_rate,
            achievement_rate=goal_achievement_rate,
            cost_efficiency_score=cost_efficiency_score,
        )
        signals: list[str] = []
        if verification_rate < 0.40:
            signals.append('weak_verification')
        if goal_achievement_rate >= 0.60:
            signals.append('high_goal_progress')
        if budget_posture.posture == 'tighten':
            signals.append('budget_tightening')
        if budget_posture.posture == 'expand_carefully':
            signals.append('budget_expansion_candidate')
        return PerformanceFeedbackPolicyView(
            execution_success_rate=execution_success_rate,
            verification_rate=verification_rate,
            goal_achievement_rate=goal_achievement_rate,
            cost_efficiency_score=cost_efficiency_score,
            budget_posture=budget_posture,
            recent_signals=tuple(signals),
        )


__all__ = ['CANON_PERFORMANCE_FEEDBACK_POLICY', 'PerformanceFeedbackPolicy', 'PerformanceFeedbackPolicyView']
