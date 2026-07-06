from __future__ import annotations

from dataclasses import dataclass

from core.economics.capital_allocation_engine import CapitalAllocationEngine, CapitalState, WorldState
from core.economics.capital_allocation_engine import CapitalPlan as AllocationPlan
from core.economics.contracts import CapitalScenarioBuilderPort, EconomicsContext
from core.economics.recommendation_policy import ensure_economics_recommendations
from kernel.decisioning.decision_types import RecommendationSet

CANON_NON_DECISION_MODULE = True

class CapitalEngine:
    """Builds capital scenarios only.

    No final allocation authority.
    No execution authority.
    """

    def __init__(self, builder: CapitalScenarioBuilderPort | None = None) -> None:
        self._builder = builder

    def build_scenarios(
        self,
        tenant_id: str,
        correlation_id: str,
        payload: dict[str, object] | None = None,
    ) -> RecommendationSet:
        if self._builder is None:
            raise RuntimeError('CapitalEngine build_scenarios requires builder')
        context = EconomicsContext(
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload=payload or {},
        )
        recommendations = self._builder.build(context)
        return ensure_economics_recommendations(recommendations)


@dataclass(frozen=True)
class CapitalDecision:
    allowed: bool
    expected_risk: float
    confidence: float
    rationale: str

    @property
    def approved(self) -> bool:
        return bool(self.allowed)


@dataclass(frozen=True)
class CapitalPolicy:
    min_confidence: float = 0.5
    max_expected_risk: float = 0.5

    def evaluate(self, plan) -> CapitalDecision:
        confidence = float(getattr(plan, 'confidence', 0.0))
        risk = float(getattr(plan, 'expected_risk', 1.0))
        allowed = confidence >= float(self.min_confidence) and risk <= float(self.max_expected_risk)
        rationale = 'capital_policy_allow' if allowed else 'capital_policy_block'
        return CapitalDecision(allowed=allowed, expected_risk=risk, confidence=confidence, rationale=rationale)


def build_capital_scenarios(
    builder: CapitalScenarioBuilderPort,
    tenant_id: str,
    correlation_id: str,
    payload: dict[str, object] | None = None,
) -> RecommendationSet:
    return CapitalEngine(builder).build_scenarios(
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        payload=payload,
    )


__all__ = [
    'AllocationPlan',
    'CapitalAllocationEngine',
    'CapitalDecision',
    'CapitalEngine',
    'CapitalPolicy',
    'CapitalState',
    'WorldState',
    'build_capital_scenarios',
]
