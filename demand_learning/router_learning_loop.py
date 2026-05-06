from __future__ import annotations

from demand_learning.policy_update_engine import PolicyUpdateEngine


class RouterLearningLoop:
    def __init__(self) -> None:
        self._engine = PolicyUpdateEngine()

    def propose_policy_updates(self, feedback_rows: tuple[dict[str, object], ...]) -> dict[str, float]:
        state = self._engine.update(feedback_rows)
        business_ids = sorted(set(state.sample_size) | set(state.causal_bonus) | set(state.risk_penalty) | set(state.fairness_boost))
        return {business_id: state.adjustment_for(business_id) for business_id in business_ids}
