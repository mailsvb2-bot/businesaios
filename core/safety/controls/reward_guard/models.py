from __future__ import annotations

from dataclasses import dataclass

from config.decision_safety_policy import DEFAULT_REWARD_GUARD_POLICY_DEFAULTS


@dataclass(frozen=True)
class RewardGuardPolicy:
    min_reward: float = DEFAULT_REWARD_GUARD_POLICY_DEFAULTS.min_reward
    min_margin: float = DEFAULT_REWARD_GUARD_POLICY_DEFAULTS.min_margin
    zero_value: float = DEFAULT_REWARD_GUARD_POLICY_DEFAULTS.zero_value
    expected_reward_key: str = DEFAULT_REWARD_GUARD_POLICY_DEFAULTS.expected_reward_key
    expected_margin_key: str = DEFAULT_REWARD_GUARD_POLICY_DEFAULTS.expected_margin_key
    blocked_reason: str = DEFAULT_REWARD_GUARD_POLICY_DEFAULTS.blocked_reason
    ok_reason: str = DEFAULT_REWARD_GUARD_POLICY_DEFAULTS.ok_reason
