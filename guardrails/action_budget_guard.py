from __future__ import annotations

from guardrails._shared import GuardCheckResult, _as_float, _as_int, _payload_view


class ActionBudgetGuard:
    def __init__(self, *, max_cost: float = 5000.0, max_actions: int = 1000) -> None:
        self._max_cost = float(max_cost)
        self._max_actions = max(1, int(max_actions))

    def check(self, payload: dict) -> tuple[bool, str]:
        body = _payload_view(payload)
        next_cost = _as_float(body.get('next_cost', body.get('estimated_cost', body.get('amount', 0.0))), minimum=0.0)
        next_actions = _as_int(body.get('next_actions', body.get('planned_actions', 1)), default=1, minimum=1)
        if next_cost > self._max_cost:
            return GuardCheckResult(False, 'action_budget_exceeded').as_tuple()
        if next_actions > self._max_actions:
            return GuardCheckResult(False, 'action_budget_actions_exceeded').as_tuple()
        return GuardCheckResult(True, 'action_budget_ok').as_tuple()
