from __future__ import annotations

from guardrails._shared import GuardCheckResult, _as_bool, _as_float, _payload_view


class RewardGuard:
    def __init__(self, *, min_reward: float = -0.25, min_margin: float = 0.0) -> None:
        self._min_reward = float(min_reward)
        self._min_margin = float(min_margin)

    def check(self, payload: dict) -> tuple[bool, str]:
        body = _payload_view(payload)
        if _as_bool(body.get('reward_hacking_detected')):
            return GuardCheckResult(False, 'reward_hacking_detected').as_tuple()
        reward = _as_float(body.get('expected_reward', body.get('reward', 0.0)))
        margin = _as_float(body.get('expected_margin', body.get('margin', 0.0)))
        if reward < self._min_reward or margin < self._min_margin:
            return GuardCheckResult(False, 'reward_guard_blocked').as_tuple()
        return GuardCheckResult(True, 'reward_guard_ok').as_tuple()
