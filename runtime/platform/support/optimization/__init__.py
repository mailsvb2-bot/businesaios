from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

CANONICAL_OPTIMIZATION_PUBLIC_MODULE = "runtime.platform.support.optimization"
COMPAT_OPTIMIZATION_DECISION_MODULE = "core.ai.decision_core"
CANON_PLATFORM_OPTIMIZATION_PUBLIC_API = True
CANON_COMPAT_SHIM = True
SOVEREIGN_DECISION_CORE = "core.ai.decision_core.DecisionCore"

class OptimizationGate(Protocol):
    def allows(self, payload: dict) -> bool:
        ...

class BudgetEnforcement:
    def within_budget(self, current_cost: float, max_cost: float) -> bool:
        return current_cost <= max_cost

class CandidateGenerator:
    def generate(self, base_config: dict, update: dict) -> dict:
        merged = dict(base_config)
        merged.update(update)
        return merged

class CandidateRegistry:
    def __init__(self) -> None:
        self._items: dict[str, dict] = {}

    def register(self, candidate_id: str, payload: dict) -> None:
        self._items[candidate_id] = dict(payload)

    def get(self, candidate_id: str) -> dict:
        return dict(self._items[candidate_id])

class CandidateScoring:
    def score(self, metrics: dict[str, float], objective: str = "score") -> float:
        return float(metrics.get(objective, 0.0))

class FallbackPolicy:
    def fallback_to(self, incumbent_id: str | None) -> str | None:
        return incumbent_id

class IncumbentRegistry:
    def __init__(self) -> None:
        self._incumbent_id: str | None = None

    def set(self, candidate_id: str) -> None:
        self._incumbent_id = candidate_id

    def get(self) -> str | None:
        return self._incumbent_id

class IterationPlanner:
    def plan(self, iteration: int) -> dict[str, int]:
        return {"iteration": iteration + 1}

@dataclass(frozen=True)
class NextIterationDecision:
    continue_running: bool

@dataclass(frozen=True)
class OptimizationRequest:
    candidate_id: str

@dataclass(frozen=True)
class OptimizationResult:
    candidate_id: str
    accepted: bool

@dataclass(frozen=True)
class OptimizerIdentity:
    name: str

from runtime.platform.support.optimization.promotion_decision import PromotionDecision

@dataclass(frozen=True)
class RollbackDecision:
    candidate_id: str
    rollback: bool

class SearchSpace:
    def __init__(self, values: dict[str, list]) -> None:
        self.values = {key: list(value) for key, value in values.items()}

class OptimizationDecisionService:
    def __init__(self, promotion_gate=None, rollback_gate=None, search_constraints=None) -> None:
        from runtime.platform.support.optimization.gates.promotion_gate import PromotionGate
        from runtime.platform.support.optimization.gates.rollback_gate import RollbackGate
        from runtime.platform.support.optimization.search_constraints import SearchConstraints
        self._promotion_gate = promotion_gate or PromotionGate()
        self._rollback_gate = rollback_gate or RollbackGate()
        self._search_constraints = search_constraints or SearchConstraints()

    def decide_promotion(self, candidate_id: str, payload: dict) -> PromotionDecision:
        normalized_candidate_id = self._normalize_candidate_id(candidate_id)
        normalized_payload = self._normalize_payload(payload)
        constraints = normalized_payload.get("search_constraints")
        if constraints is not None and not self._search_constraints.valid(constraints):
            return PromotionDecision(candidate_id=normalized_candidate_id, approved=False, reason='invalid_search_constraints')
        approved = self._promotion_gate.allows(normalized_payload)
        return PromotionDecision(candidate_id=normalized_candidate_id, approved=approved, reason='' if approved else 'promotion_gate_blocked')

    def decide_rollback(self, candidate_id: str, payload: dict) -> RollbackDecision:
        normalized_candidate_id = self._normalize_candidate_id(candidate_id)
        normalized_payload = self._normalize_payload(payload)
        return RollbackDecision(candidate_id=normalized_candidate_id, rollback=self._rollback_gate.allows(normalized_payload))

    @staticmethod
    def _normalize_candidate_id(candidate_id: str) -> str:
        normalized = str(candidate_id).strip()
        if not normalized:
            raise ValueError('candidate_id is required')
        return normalized

    @staticmethod
    def _normalize_payload(payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise TypeError('payload must be a dict')
        return dict(payload)

class SelfOptimizationLoop:
    def __init__(self, decision_service: OptimizationDecisionService | None = None) -> None:
        self._decision_service = decision_service or OptimizationDecisionService()

    def run(self, candidate_id: str, payload: dict) -> OptimizationResult:
        decision = self._decision_service.decide_promotion(candidate_id, payload)
        return OptimizationResult(candidate_id=decision.candidate_id, accepted=decision.approved)

_ALIAS_EXPORTS = {
    "budget_enforcement": "BudgetEnforcement",
    "candidate_generator": "CandidateGenerator",
    "candidate_registry": "CandidateRegistry",
    "candidate_scoring": "CandidateScoring",
    "contracts": "OptimizationGate",
    "fallback_policy": "FallbackPolicy",
    "incumbent_registry": "IncumbentRegistry",
    "iteration_planner": "IterationPlanner",
    "next_iteration_decision": "NextIterationDecision",
    "optimization_request": "OptimizationRequest",
    "optimization_result": "OptimizationResult",
    "optimizer_identity": "OptimizerIdentity",
    "promotion_decision": "PromotionDecision",
    "rollback_decision": "RollbackDecision",
    "search_space": "SearchSpace",
    "service": "OptimizationDecisionService",
    "self_optimization_loop": "SelfOptimizationLoop",
}

__all__ = (
    "BudgetEnforcement",
    "CANON_COMPAT_SHIM",
    "CANON_PLATFORM_OPTIMIZATION_PUBLIC_API",
    "CandidateGenerator",
    "CandidateRegistry",
    "CandidateScoring",
    "COMPAT_OPTIMIZATION_DECISION_MODULE",
    "FallbackPolicy",
    "IncumbentRegistry",
    "IterationPlanner",
    "NextIterationDecision",
    "OptimizationDecisionService",
    "OptimizationGate",
    "OptimizationRequest",
    "OptimizationResult",
    "OptimizerIdentity",
    "PromotionDecision",
    "RollbackDecision",
    "SOVEREIGN_DECISION_CORE",
    "SearchSpace",
    "SelfOptimizationLoop",
)
