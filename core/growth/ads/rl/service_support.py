from __future__ import annotations

from typing import Any, Dict

from .contextual_bandit_policy import action_key
from .contracts import AdsRLAction, AdsRLState, AdsRLSuggestion, AdsRLOptSpec


Json = Dict[str, Any]


def build_seed(*, tenant_id: str, spec: AdsRLOptSpec, seed: str) -> str:
    return f"{tenant_id}|{spec.platform}|{spec.campaign_id}|{seed}"


def recent_mean_reward(stats: Any) -> float | None:
    try:
        pulls = 0
        reward_sum = 0.0
        for stat in (stats or {}).values():
            pulls += int(stat.pulls)
            reward_sum += float(stat.reward_sum)
        if pulls <= 0:
            return None
        return float(reward_sum) / float(pulls)
    except Exception:
        return None


def state_to_public(state: AdsRLState) -> Json:
    return {
        "platform": str(state.platform),
        "campaign_id": str(state.campaign_id),
        "ts_ms": int(state.ts_ms),
        "impressions": int(state.impressions),
        "clicks": int(state.clicks),
        "leads": int(state.leads),
        "purchases": int(state.purchases),
        "spend": float(state.spend),
        "revenue": float(state.revenue),
        "day_of_week": int(state.day_of_week),
        "hour_of_day": int(state.hour_of_day),
    }


def suggestion_to_public(*, suggestion: AdsRLSuggestion) -> Json:
    return {
        "policy_id": suggestion.policy_id,
        "action": suggestion.action.to_json(),
        "action_key": action_key(suggestion.action),
        "confidence": float(suggestion.confidence),
        "reason": suggestion.reason,
        "canary": bool(suggestion.canary),
        "allow_apply": bool(suggestion.allow_apply),
        "safety_reason": suggestion.safety_reason,
    }


def report_to_public(*, campaign_id: str, steps: list[Any]) -> Json:
    rewards = [float(step.reward) for step in steps if step.reward is not None]
    mean_reward = sum(rewards) / max(1, len(rewards)) if rewards else 0.0
    return {
        "status": "ok",
        "campaign_id": str(campaign_id),
        "n": int(len(rewards)),
        "mean_reward": float(mean_reward),
        "recent": [
            {
                "ts_ms": int(step.ts_ms),
                "policy_id": step.policy_id,
                "action_key": step.action_key,
                "reward": step.reward,
                "reward_mode": step.reward_mode,
            }
            for step in steps[:50]
        ],
    }


__all__ = [
    "Json",
    "build_seed",
    "recent_mean_reward",
    "report_to_public",
    "state_to_public",
    "suggestion_to_public",
]
