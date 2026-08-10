from __future__ import annotations

from typing import Mapping

from config.risk_evaluation_policy import DEFAULT_FRAUD_RISK_TRACKER_POLICY


class FraudRiskTracker:
    def score(self, outcome: Mapping[str, object]) -> float:
        policy = DEFAULT_FRAUD_RISK_TRACKER_POLICY
        score = 0.0
        if outcome.get('fraud_flag'):
            score += policy.fraud_flag_weight
        if outcome.get('duplicate_flag'):
            score += policy.duplicate_flag_weight
        if outcome.get('source_spoof_flag'):
            score += policy.source_spoof_flag_weight
        if outcome.get('existing_customer_flag'):
            score += policy.existing_customer_flag_weight
        return min(policy.score_ceiling, round(score, 4))

    def penalty(self, outcome: dict[str, object]) -> float:
        policy = DEFAULT_FRAUD_RISK_TRACKER_POLICY
        score = self.score(outcome)
        if score >= policy.high_penalty_threshold:
            return policy.high_penalty
        if score >= policy.medium_penalty_threshold:
            return policy.medium_penalty
        if score >= policy.low_penalty_threshold:
            return policy.low_penalty
        return policy.zero_penalty
