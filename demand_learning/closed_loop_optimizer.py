from __future__ import annotations

from config.learning_thresholds import POLICY_CHANGE_EPSILON, POLICY_MIN_OUTCOME_ROWS_FOR_UPDATE
from demand_learning.policy_state import PolicyState
from demand_learning.policy_update_engine import PolicyUpdateEngine


class ClosedLoopOptimizer:
    def __init__(self) -> None:
        self._engine = PolicyUpdateEngine()
        self._state = PolicyState()
        self._history: list[PolicyState] = []

    def current_state(self) -> PolicyState:
        return self._state

    def history(self) -> tuple[PolicyState, ...]:
        return tuple(self._history)

    def _material_change(self, next_state: PolicyState) -> bool:
        keys = set(self._state.sample_size) | set(next_state.sample_size)
        for business_id in keys:
            if abs(self._state.adjustment_for(business_id) - next_state.adjustment_for(business_id)) > POLICY_CHANGE_EPSILON:
                return True
            if self._state.sample_size.get(business_id, 0) != next_state.sample_size.get(business_id, 0):
                return True
        return False

    def learn(self, outcome_rows: tuple[dict[str, object], ...]) -> PolicyState:
        if len(outcome_rows) < POLICY_MIN_OUTCOME_ROWS_FOR_UPDATE:
            return self._state
        next_state = self._engine.update(outcome_rows)
        if self._material_change(next_state):
            self._state = next_state
            self._history.append(next_state)
        return self._state
