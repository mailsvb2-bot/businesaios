from __future__ import annotations

"""Canonical demand guard policy primitives.

This module is the single policy home for demand-side safety checks. The
legacy ``demand_guardrails`` package remains as a transition-only import
surface so stable imports continue to work while policy truth stays in one
place.
"""

from config.demand_thresholds import (
    BAD_OUTCOME_ROLLBACK_THRESHOLD,
    HIGH_RISK_BUSINESS_THRESHOLD,
    MAX_LOAD_RATIO,
    MONOPOLY_LIMIT,
    NO_RESPONSE_RATE_LIMIT,
    REPUTATION_FLOOR,
)
from guardrails._threshold_primitives import greater_equal, less_equal, less_than, score_or_zero
from config.risk_evaluation_policy import DEFAULT_FRAUD_PATTERN_RISK_POLICY


class DemandDecisionGuard:
    """Demand admission gate composed from shared guard threshold primitives."""

    def allow(self, *, live_state) -> tuple[bool, tuple[str, ...]]:
        reasons: list[str] = []
        if not less_than(live_state.risk_score, HIGH_RISK_BUSINESS_THRESHOLD):
            reasons.append(f"risk>={HIGH_RISK_BUSINESS_THRESHOLD:.2f}")
        if not greater_equal(live_state.reputation_score, REPUTATION_FLOOR):
            reasons.append(f"reputation<{REPUTATION_FLOOR:.2f}")
        if not less_equal(1.0 - float(live_state.capacity_score), MAX_LOAD_RATIO):
            reasons.append(f"load>{MAX_LOAD_RATIO:.2f}")
        if not less_equal(1.0 - float(live_state.response_speed_score), NO_RESPONSE_RATE_LIMIT):
            reasons.append(f"no_response>{NO_RESPONSE_RATE_LIMIT:.2f}")
        return not reasons, tuple(reasons)


class FraudPatternGuard:
    def evaluate(self, fraud_risk) -> tuple[bool, float, tuple[str, ...]]:
        if isinstance(fraud_risk, dict):
            policy = DEFAULT_FRAUD_PATTERN_RISK_POLICY
            duplicate_hits = int(fraud_risk.get('duplicate_hits', 0) or 0)
            velocity = float(fraud_risk.get('velocity_score', 0.0) or 0.0)
            spoof = float(fraud_risk.get('source_spoof_score', 0.0) or 0.0)
            prior = float(fraud_risk.get('fraud_risk', 0.0) or 0.0)
            risk_score = min(policy.score_ceiling, prior + (policy.duplicate_hit_weight * duplicate_hits) + (policy.velocity_weight * velocity) + (policy.source_spoof_weight * spoof))
            reasons: list[str] = []
            if duplicate_hits:
                reasons.append(f'duplicate_hits={duplicate_hits}')
            if velocity >= policy.high_velocity_threshold:
                reasons.append('high_velocity_pattern')
            if spoof >= policy.source_spoof_threshold:
                reasons.append('source_spoof_risk')
            if not reasons:
                reasons.append('no_material_pattern_found')
            return risk_score < HIGH_RISK_BUSINESS_THRESHOLD, round(risk_score, 4), tuple(reasons)
        try:
            score = float(fraud_risk)
        except (TypeError, ValueError):
            score = 0.0
        reason = 'threshold_ok' if score < HIGH_RISK_BUSINESS_THRESHOLD else 'threshold_block'
        return score < HIGH_RISK_BUSINESS_THRESHOLD, round(score, 4), (reason,)

    def check(self, fraud_risk) -> object:
        return self.evaluate(fraud_risk)[0]


class NoMonopolyGuard:
    def check(self, concentration_ratio) -> object:
        return less_equal(concentration_ratio, MONOPOLY_LIMIT)


class RollbackGuard:
    def check(self, bad_outcome_ratio) -> object:
        return greater_equal(bad_outcome_ratio, BAD_OUTCOME_ROLLBACK_THRESHOLD)


class RoutingRiskGuard:
    def check(self, candidate) -> object:
        return score_or_zero(score=getattr(candidate, 'rank_score', 0.0), blocked=getattr(candidate, 'blocked', False))


class CustomerFitGuard:
    def check(self, candidate) -> object:
        policy = DEFAULT_FRAUD_PATTERN_RISK_POLICY
        return bool(not getattr(candidate, 'blocked', False) and greater_equal(getattr(candidate, 'rank_score', 0.0), policy.customer_fit_rank_floor))


__all__ = [
    'CustomerFitGuard',
    'DemandDecisionGuard',
    'FraudPatternGuard',
    'NoMonopolyGuard',
    'RollbackGuard',
    'RoutingRiskGuard',
]
