from __future__ import annotations

import shared.numbers as _shared_numbers
from config.decision_safety_policy import DEFAULT_DECISION_VALIDATOR_POLICY, DecisionValidatorPolicy
from core.constraints.decision import DecisionConstraints
from kernel.decision_candidate import DecisionCandidate


class DecisionValidator:
    def __init__(self, policy: DecisionValidatorPolicy | None = None) -> None:
        self._policy = policy or DEFAULT_DECISION_VALIDATOR_POLICY

    def validate(self, candidate: DecisionCandidate, constraints: DecisionConstraints) -> tuple[bool, str]:
        payload = candidate.payload if isinstance(candidate.payload, dict) else {}
        budget_delta = _shared_numbers.coerce_float(payload.get('budget_delta'), self._policy.zero_budget_delta, minimum=self._policy.zero_budget_delta)
        risk_score = _shared_numbers.coerce_float(
            payload.get('risk_score'),
            self._policy.zero_risk_score,
            minimum=self._policy.zero_risk_score,
            maximum=self._policy.risk_score_ceiling,
        )
        if candidate.confidence < constraints.min_confidence:
            return False, 'confidence_below_threshold'
        if budget_delta > constraints.max_budget_delta:
            return False, 'budget_delta_too_high'
        if risk_score > constraints.max_risk_score:
            return False, 'risk_score_too_high'
        if candidate.channel in constraints.forbidden_channels:
            return False, 'forbidden_channel'
        if candidate.action_type.strip() != candidate.action_type or not candidate.action_type:
            return False, 'invalid_action_type'
        if candidate.action_type == self._policy.route_lead_action_type:
            business_id = str(payload.get('business_id') or '').strip()
            if not business_id:
                return False, 'missing_business_id'
            rank_score = _shared_numbers.coerce_float(
                payload.get('rank_score', candidate.score),
                candidate.score,
                minimum=self._policy.zero_rank_score,
            )
            if rank_score <= self._policy.zero_rank_score:
                return False, 'rank_score_too_low'
        return True, 'ok'
