from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config.ads_rl_policy import DEFAULT_ADS_RL_SERVICE_POLICY, AdsRLServicePolicy
from core.ads.ads_service import AdsService
import learning.rollout as _learning_rollout

from .action_space import build_action_space
from .contracts import AdsRLAction, AdsRLState, AdsRLSuggestion, AdsRLOptSpec
from .contextual_bandit_policy import UCB1Policy
from .experience_store import AdsRLExperienceStore
from .reward import compute_reward
from .safety import decide_safety
from .service_support import (
    Json,
    build_seed,
    recent_mean_reward,
    report_to_public,
    state_to_public,
    suggestion_to_public,
)
from .state_builder import build_state_from_ads_metrics
from .plan_builder import to_ads_plan


@dataclass(frozen=True)
class AdsRLOptimizerDeps:
    ads: AdsService
    event_store: Any
    rollout_guard: _learning_rollout.RolloutGuard | None = None
    policy: AdsRLServicePolicy = field(default_factory=lambda: DEFAULT_ADS_RL_SERVICE_POLICY)


class AdsRLOptimizerService:
    """Production-safe Ads RL Optimizer.

    Advisory only: DecisionCore remains the single decision issuer.
    """

    def __init__(self, deps: AdsRLOptimizerDeps) -> None:
        self._ads = deps.ads
        self._exp = AdsRLExperienceStore(deps.event_store)
        self._rollout_guard = deps.rollout_guard
        self._policy = deps.policy

    def suggest(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        spec: AdsRLOptSpec,
        current_daily_budget: float | None = None,
        seed: str = "",
        meta: Json | None = None,
    ) -> Json:
        ok, why = spec.validate()
        if not ok:
            return {"status": "error", "reason": why}

        state = self._build_state_from_ads_metrics(tenant_id=tenant_id, spec=spec)
        actions, stats = build_action_space(spec)
        if not actions:
            return {"status": "error", "reason": "empty_action_space"}

        arm_stats = self._exp.compute_arm_stats(
            tenant_id=tenant_id,
            campaign_id=spec.campaign_id,
            limit=self._policy.arm_stats_limit,
        )
        rollout_seed = build_seed(tenant_id=tenant_id, spec=spec, seed=seed)
        policy = UCB1Policy(policy_id="ads_ucb1@v1", stats=arm_stats, seed=rollout_seed)
        policy_decision = policy.select_action(state=state, actions=actions)
        propensity = self._policy.propensity_numerator / max(self._policy.default_propensity_denominator_floor, len(actions))
        safety = decide_safety(
            spec=spec,
            action=policy_decision.action,
            policy_id=policy_decision.policy_id,
            recent_reward=recent_mean_reward(arm_stats),
            current_daily_budget=current_daily_budget,
            rollout_seed=rollout_seed,
            rollout_guard=self._rollout_guard,
            safety_policy=self._policy.safety_policy,
        )
        suggestion = AdsRLSuggestion(
            policy_id=policy_decision.policy_id,
            action=policy_decision.action,
            confidence=float(policy_decision.confidence),
            reason=str(policy_decision.reason),
            canary=bool(spec.canary),
            allow_apply=bool(safety.allow_apply),
            safety_reason=str(safety.reason),
        )
        self._exp.append_suggested(
            tenant_id=str(tenant_id),
            user_id=user_id,
            suggestion=suggestion,
            state=state,
            meta={
                **dict(meta or {}),
                "propensity": float(propensity),
                "action_space_n": int(stats.n_actions),
                "truncated": bool(stats.truncated),
            },
        )
        plan = self._to_ads_plan(spec=spec, suggestion=suggestion)
        return {
            "status": "ok",
            "note": "advisory_suggestion_only",
            "state": state_to_public(state),
            "suggestion": suggestion_to_public(suggestion=suggestion),
            "plan": {"commands": [command.__dict__ for command in plan.commands], "notes": plan.notes},
        }

    def observe(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        spec: AdsRLOptSpec,
        policy_id: str,
        action: AdsRLAction,
        meta: Json | None = None,
    ) -> Json:
        ok, why = spec.validate()
        if not ok:
            return {"status": "error", "reason": why}
        state = self._build_state_from_ads_metrics(tenant_id=tenant_id, spec=spec)
        reward_breakdown = compute_reward(state=state, spec=spec, policy=self._policy.reward_policy)
        self._exp.append_observed(
            tenant_id=str(tenant_id),
            user_id=user_id,
            policy_id=str(policy_id),
            state=state,
            action=action,
            reward=reward_breakdown,
            meta=dict(meta or {}),
        )
        return {
            "status": "ok",
            "reward": float(reward_breakdown.reward),
            "mode": reward_breakdown.mode,
            "components": reward_breakdown.components,
            "state": state_to_public(state),
        }

    def report(self, *, tenant_id: str, campaign_id: str, limit: int | None = None) -> Json:
        effective_limit = self._policy.default_report_limit if limit is None else int(limit)
        steps = self._exp.load_recent_observed(
            tenant_id=str(tenant_id),
            campaign_id=str(campaign_id),
            limit=effective_limit,
        )
        return report_to_public(campaign_id=campaign_id, steps=steps)

    def _build_state_from_ads_metrics(self, *, tenant_id: str, spec: AdsRLOptSpec) -> AdsRLState:
        return build_state_from_ads_metrics(ads_service=self._ads, tenant_id=tenant_id, spec=spec)

    def _to_ads_plan(self, *, spec: AdsRLOptSpec, suggestion: AdsRLSuggestion):
        return to_ads_plan(spec=spec, suggestion=suggestion)
