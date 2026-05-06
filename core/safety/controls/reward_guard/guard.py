from __future__ import annotations

from ..action_context import SafetyActionContext
from ..control_result import ControlDecision, ControlStatus
from .models import RewardGuardPolicy


class RewardGuard:
    control_name = "reward_guard"

    def __init__(self, policy: RewardGuardPolicy | None = None):
        self._policy = policy or RewardGuardPolicy()

    def evaluate(self, ctx: SafetyActionContext) -> ControlDecision:
        payload = dict(ctx.payload)
        reward = float(payload.get(self._policy.expected_reward_key, self._policy.zero_value) or self._policy.zero_value)
        margin = float(payload.get(self._policy.expected_margin_key, self._policy.zero_value) or self._policy.zero_value)
        if reward < self._policy.min_reward or margin < self._policy.min_margin:
            return ControlDecision(
                control=self.control_name,
                status=ControlStatus.BLOCK,
                reason=self._policy.blocked_reason,
                details={self._policy.expected_reward_key: reward, self._policy.expected_margin_key: margin},
            )
        return ControlDecision(control=self.control_name, status=ControlStatus.ALLOW, reason=self._policy.ok_reason)
