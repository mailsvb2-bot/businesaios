from __future__ import annotations

import hashlib
from dataclasses import dataclass

import learning.rollout as _learning_rollout
from config.ads_rl_policy import DEFAULT_ADS_RL_SAFETY_POLICY, AdsRLSafetyPolicy

from .contracts import AdsRLAction, AdsRLOptSpec


@dataclass(frozen=True)
class SafetyVerdict:
    allow_apply: bool
    reason: str


def rollout_bucket(*, seed: str, policy: AdsRLSafetyPolicy = DEFAULT_ADS_RL_SAFETY_POLICY) -> float:
    """Deterministic bucket in [0, 100)."""
    h = hashlib.sha256(str(seed).encode("utf-8")).digest()
    x = int.from_bytes(h[:8], "big", signed=False)
    return (x % policy.rollout_bucket_modulus) / policy.rollout_bucket_divisor


def enforce_rollout_pct(*, rollout_pct: float, seed: str, policy: AdsRLSafetyPolicy = DEFAULT_ADS_RL_SAFETY_POLICY) -> bool:
    pct = float(rollout_pct)
    if pct <= policy.rollout_pct_floor:
        return False
    if pct >= policy.rollout_pct_ceiling:
        return True
    return rollout_bucket(seed=seed, policy=policy) < pct


def budget_increase_ok(
    *,
    current_budget: float | None,
    proposed_budget: float | None,
    max_increase_pct: float,
    policy: AdsRLSafetyPolicy = DEFAULT_ADS_RL_SAFETY_POLICY,
) -> bool:
    if proposed_budget is None:
        return True
    if current_budget is None:
        return True
    try:
        cur = float(current_budget)
        prop = float(proposed_budget)
    except Exception:
        return True
    if cur <= policy.non_positive_budget_floor:
        return True
    pct = ((prop - cur) / cur) * policy.percent_multiplier
    return pct <= float(max_increase_pct)


def decide_safety(
    *,
    spec: AdsRLOptSpec,
    action: AdsRLAction,
    policy_id: str,
    recent_reward: float | None,
    current_daily_budget: float | None,
    rollout_seed: str,
    rollout_guard: _learning_rollout.RolloutGuard | None,
    safety_policy: AdsRLSafetyPolicy = DEFAULT_ADS_RL_SAFETY_POLICY,
) -> SafetyVerdict:
    """Return whether action is allowed to apply (otherwise plan-only)."""
    if not budget_increase_ok(
        current_budget=current_daily_budget,
        proposed_budget=action.daily_budget,
        max_increase_pct=float(spec.max_budget_increase_pct),
        policy=safety_policy,
    ):
        return SafetyVerdict(False, "budget_increase_pct_exceeded")

    # Rollout gate: even safe action might be plan-only if user is outside canary bucket.
    if bool(spec.canary) and not enforce_rollout_pct(rollout_pct=float(spec.rollout_pct), seed=str(rollout_seed), policy=safety_policy):
        return SafetyVerdict(False, "canary_bucket_blocked")

    # Central rollout guard (DecisionCore-level) as extra safety.
    if rollout_guard is not None:
        rd = rollout_guard.allow_rollout(policy_id=str(policy_id), canary=bool(spec.canary), recent_reward=recent_reward)
        if not bool(rd.allow):
            return SafetyVerdict(False, f"rollout_guard:{rd.reason}")

    return SafetyVerdict(True, "ok")
