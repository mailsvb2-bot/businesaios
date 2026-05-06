from __future__ import annotations

from guardrails._shared import GuardCheckResult, _as_int, _payload_view


class DailyActionLimitGuard:
    def __init__(self, *, max_actions_per_day: int = 100) -> None:
        self._max_actions_per_day = max(1, int(max_actions_per_day))

    def check(self, payload: dict) -> tuple[bool, str]:
        body = _payload_view(payload)
        current = _as_int(body.get('daily_action_count', body.get('action_count_today', 0)), minimum=0)
        planned = _as_int(body.get('planned_actions', 1), default=1, minimum=1)
        if current + planned > self._max_actions_per_day:
            return GuardCheckResult(False, 'daily_action_limit_exceeded').as_tuple()
        return GuardCheckResult(True, 'daily_action_limit_ok').as_tuple()
