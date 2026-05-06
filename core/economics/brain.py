from __future__ import annotations

CANON_NON_DECISION_MODULE = True

from dataclasses import dataclass

from config.economics_domain_policy import (
    DEFAULT_ECONOMIC_BRAIN_POLICY,
    DEFAULT_ECONOMICS_SIGNAL_DEFAULTS,
    DEFAULT_LTV_ESTIMATOR_POLICY,
    EconomicBrainPolicy,
    LTVEstimatorPolicy,
)

from kernel.decisioning.decision_types import RecommendationSet
from core.economics.contracts import EconomicsContext, EconomicsRecommendationBuilderPort
from core.economics.recommendation_policy import ensure_economics_recommendations
from core.economics.types import EconomicAction, EconomicState
from core.strategic_horizon.engine import StrategicMode


@dataclass(frozen=True)
class EconomicSignals:
    ltv: float
    pricing: EconomicAction
    growth: EconomicAction
    reward: float


class LTVEstimator:
    def __init__(self, policy: LTVEstimatorPolicy | None = None) -> None:
        self._policy = policy or DEFAULT_LTV_ESTIMATOR_POLICY

    def estimate(self, state: EconomicState) -> float:
        gross = float(state.revenue) - float(state.cost)
        return max(self._policy.zero_value, float(state.retention_prob) * gross)


class PricingPolicy:
    def __init__(self, policy: EconomicBrainPolicy | None = None) -> None:
        self._policy = policy or DEFAULT_ECONOMIC_BRAIN_POLICY

    def recommend(self, state: EconomicState, *, ltv: float) -> EconomicAction:
        retention = float(state.retention_prob)
        policy = self._policy
        if retention < policy.retention_discount_threshold:
            return EconomicAction(kind="discount", value=policy.discount_value)
        if retention >= policy.retention_upsell_threshold and ltv > policy.reward_floor:
            return EconomicAction(kind="upsell", value=policy.upsell_value)
        return EconomicAction(kind="keep", value=policy.keep_value)


class GrowthPolicy:
    def __init__(self, policy: EconomicBrainPolicy | None = None) -> None:
        self._policy = policy or DEFAULT_ECONOMIC_BRAIN_POLICY

    def recommend(self, state: EconomicState, *, ltv: float) -> EconomicAction:
        retention = float(state.retention_prob)
        policy = self._policy
        if retention < policy.retention_discount_threshold:
            return EconomicAction(kind=StrategicMode.STABILIZE.value, value=policy.stabilize_value)
        if retention >= policy.retention_upsell_threshold and ltv > policy.reward_floor:
            return EconomicAction(kind=StrategicMode.EXPAND.value, value=policy.expand_value)
        return EconomicAction(kind=StrategicMode.OPTIMIZE.value, value=policy.optimize_value)


class EconomicReward:
    def __init__(self, policy: EconomicBrainPolicy | None = None) -> None:
        self._policy = policy or DEFAULT_ECONOMIC_BRAIN_POLICY

    def compute(self, state: EconomicState, *, ltv: float, pricing: EconomicAction, growth: EconomicAction) -> float:
        penalty_multiplier = self._policy.penalty_multiplier
        pricing_penalty = abs(float(pricing.value)) * penalty_multiplier
        growth_penalty = abs(float(growth.value)) * penalty_multiplier
        return max(self._policy.reward_floor, float(ltv) - pricing_penalty - growth_penalty)


class EconomicsBrain:
    def __init__(self, builder: EconomicsRecommendationBuilderPort) -> None:
        self._builder = builder

    def analyze(self, tenant_id: str, correlation_id: str, payload: dict[str, object] | None = None) -> RecommendationSet:
        context = EconomicsContext(tenant_id=tenant_id, correlation_id=correlation_id, payload=payload or {})
        recommendations = self._builder.build(context)
        return ensure_economics_recommendations(recommendations)


class EconomicBrain:
    def __init__(self, ltv: LTVEstimator | None = None, pricing: PricingPolicy | None = None, growth: GrowthPolicy | None = None, reward: EconomicReward | None = None, policy: EconomicBrainPolicy | None = None) -> None:
        policy = policy or DEFAULT_ECONOMIC_BRAIN_POLICY
        self._ltv = ltv or LTVEstimator()
        self._pricing = pricing or PricingPolicy(policy=policy)
        self._growth = growth or GrowthPolicy(policy=policy)
        self._reward = reward or EconomicReward(policy=policy)
        self._signal_defaults = DEFAULT_ECONOMICS_SIGNAL_DEFAULTS

    def signals(self, state: EconomicState) -> EconomicSignals:
        ltv = float(self._ltv.estimate(state))
        pricing = self._pricing.recommend(state, ltv=ltv)
        growth = self._growth.recommend(state, ltv=ltv)
        reward = float(self._reward.compute(state, ltv=ltv, pricing=pricing, growth=growth))
        return EconomicSignals(ltv=ltv, pricing=pricing, growth=growth, reward=reward)

    def components(self, state: EconomicState) -> tuple[float, float, float]:
        signals = self.signals(state)
        spend = max(self._signal_defaults.zero_amount, float(state.cost))
        return float(signals.ltv), spend, float(signals.reward)

    def step(self, state: EconomicState) -> float:
        return float(self.signals(state).reward)


def analyze_economics(builder: EconomicsRecommendationBuilderPort, tenant_id: str, correlation_id: str, payload: dict[str, object] | None = None) -> RecommendationSet:
    return EconomicsBrain(builder).analyze(tenant_id=tenant_id, correlation_id=correlation_id, payload=payload)


__all__ = ["EconomicBrain", "EconomicReward", "EconomicSignals", "EconomicsBrain", "GrowthPolicy", "LTVEstimator", "PricingPolicy", "analyze_economics"]
