from __future__ import annotations

CANON_NON_DECISION_MODULE = True

from dataclasses import dataclass
from math import exp

from config.economics_domain_policy import DEFAULT_CAPITAL_ALLOCATION_POLICY, CapitalAllocationPolicy

from kernel.decisioning.decision_types import RecommendationSet
from core.economics.contracts import CapitalAllocationSelectorPort, EconomicsContext
from core.economics.recommendation_policy import ensure_economics_recommendations


@dataclass(frozen=True)
class CapitalState:
    cash_balance: float
    marketing_budget: float
    compute_budget: float
    risk_limits: float
    runway_days: float
    reserve: float


@dataclass(frozen=True)
class WorldState:
    capital: CapitalState
    ltv: float
    cac: float
    growth_rate: float
    churn_rate: float
    uncertainty: float


@dataclass(frozen=True)
class Allocation:
    target: str
    amount: float
    capital_type: str
    risk_class: str


@dataclass(frozen=True)
class CapitalPlan:
    allocations: tuple[Allocation, ...]
    horizon_days: int
    confidence: float
    expected_risk: float
    expected_value: float


@dataclass(frozen=True)
class Constraints:
    reserve_required: float
    max_spend: float
    min_runway_days: int


class DefaultRiskModel:
    def __init__(self, policy: CapitalAllocationPolicy | None = None) -> None:
        self._policy = policy or DEFAULT_CAPITAL_ALLOCATION_POLICY

    def estimate(self, world: WorldState) -> float:
        policy = self._policy
        runway_risk = policy.one_value / max(float(world.capital.runway_days), policy.runway_days_floor)
        return min(policy.one_value, max(policy.zero_value, runway_risk + float(world.churn_rate) + float(world.uncertainty)))


class ConstraintBuilder:
    def __init__(self, policy: CapitalAllocationPolicy | None = None) -> None:
        self._policy = policy or DEFAULT_CAPITAL_ALLOCATION_POLICY

    def from_world(self, world: WorldState) -> Constraints:
        reserve_required = self._policy.reserve_ratio * float(world.capital.cash_balance)
        max_spend = max(self._policy.zero_value, float(world.capital.cash_balance) - reserve_required)
        return Constraints(
            reserve_required=reserve_required,
            max_spend=max_spend,
            min_runway_days=self._policy.min_runway_days,
        )


class CapitalAllocationEngine:
    """Canonical recommendation scorer plus deterministic compat allocator."""

    economics_recommendation_set_only = True

    def __init__(self, selector: CapitalAllocationSelectorPort | None = None, policy: CapitalAllocationPolicy | None = None) -> None:
        self._selector = selector
        self._policy = policy or DEFAULT_CAPITAL_ALLOCATION_POLICY
        self._risk_model = DefaultRiskModel(policy=self._policy)
        self._constraints = ConstraintBuilder(policy=self._policy)

    def score_options(
        self,
        tenant_id: str,
        correlation_id: str,
        payload: dict[str, object] | None = None,
    ) -> RecommendationSet:
        if self._selector is None:
            raise RuntimeError("CapitalAllocationEngine score_options requires selector")
        context = EconomicsContext(
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload=payload or {},
        )
        recommendations = self._selector.select(context)
        return ensure_economics_recommendations(recommendations)

    def rank_options(
        self,
        tenant_id: str,
        correlation_id: str,
        payload: dict[str, object] | None = None,
    ) -> RecommendationSet:
        return self.score_options(
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload=payload,
        )

    def allow_spend(self, decision_cost: float, capital: CapitalState) -> bool:
        zero_value = self._policy.zero_value
        world = WorldState(
            capital=capital,
            ltv=zero_value,
            cac=zero_value,
            growth_rate=zero_value,
            churn_rate=zero_value,
            uncertainty=zero_value,
        )
        constraints = self._constraints.from_world(world)
        return float(decision_cost) <= min(constraints.max_spend, float(capital.marketing_budget))

    def allocate(self, world: WorldState) -> CapitalPlan:
        policy = self._policy
        risk = self._risk_model.estimate(world)
        constraints = self._constraints.from_world(world)

        if float(world.capital.runway_days) < constraints.min_runway_days or risk > policy.shutdown_risk_threshold:
            return CapitalPlan(
                allocations=(
                    Allocation(
                        target=policy.reserve_target,
                        amount=float(world.capital.cash_balance),
                        capital_type=policy.cash_capital_type,
                        risk_class=policy.minimal_risk_class,
                    ),
                ),
                horizon_days=policy.reserve_horizon_days,
                confidence=max(policy.zero_value, policy.one_value - risk),
                expected_risk=risk,
                expected_value=policy.zero_value,
            )

        spend = min(constraints.max_spend, max(policy.zero_value, float(world.capital.marketing_budget)))
        value = policy.zero_value
        if float(world.cac) > policy.zero_value:
            value = max(policy.zero_value, (float(world.ltv) / float(world.cac) - policy.value_margin_offset) * max(policy.zero_value, float(world.growth_rate)))
        x = max(policy.logistic_floor, min(policy.logistic_ceiling, value - risk))
        confidence = policy.one_value / (policy.one_value + exp(-x))
        growth_share = max(policy.growth_share_min, min(policy.growth_share_max, confidence))
        growth_amount = spend * growth_share
        reserve_amount = max(policy.zero_value, spend - growth_amount)
        return CapitalPlan(
            allocations=(
                Allocation(target=policy.growth_target, amount=growth_amount, capital_type=policy.cash_capital_type, risk_class=policy.managed_risk_class),
                Allocation(target=policy.reserve_target, amount=reserve_amount, capital_type=policy.cash_capital_type, risk_class=policy.minimal_risk_class),
            ),
            horizon_days=policy.active_horizon_days,
            confidence=confidence,
            expected_risk=risk,
            expected_value=max(policy.zero_value, value * spend),
        )


def rank_capital_allocations(
    selector: CapitalAllocationSelectorPort,
    tenant_id: str,
    correlation_id: str,
    payload: dict[str, object] | None = None,
) -> RecommendationSet:
    return CapitalAllocationEngine(selector).score_options(
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        payload=payload,
    )


__all__ = [
    "Allocation",
    "CapitalAllocationEngine",
    "CapitalPlan",
    "CapitalState",
    "ConstraintBuilder",
    "Constraints",
    "DefaultRiskModel",
    "WorldState",
    "rank_capital_allocations",
]
