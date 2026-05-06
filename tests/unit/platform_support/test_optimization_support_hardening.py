from __future__ import annotations

from runtime.platform.support.optimization.convergence_policy import ConvergencePolicy
from runtime.platform.support.optimization.search_constraints import SearchConstraints
from runtime.platform.support.optimization.service import OptimizationDecisionService


def test_search_constraints_reject_invalid_ranges_and_negative_limits() -> None:
    constraints = SearchConstraints()
    assert constraints.valid({"iterations": 5, "budget": 0.0, "min_score": 0.1, "max_score": 0.9}) is True
    assert constraints.valid({"iterations": 0}) is False
    assert constraints.valid({"budget": -1}) is False
    assert constraints.valid({"min_score": 0.9, "max_score": 0.1}) is False
    assert constraints.valid(None) is False


def test_convergence_policy_requires_stable_window_not_single_pair() -> None:
    policy = ConvergencePolicy()
    assert policy.converged([1.0, 0.5], tolerance=0.6) is False
    assert policy.converged([1.0, 1.0004, 0.9999], tolerance=0.001) is True
    assert policy.converged([1.0, 1.5, 1.0], tolerance=0.001) is False


def test_optimization_service_blocks_invalid_search_constraints_before_gate() -> None:
    service = OptimizationDecisionService()
    decision = service.decide_promotion(
        " candidate-1 ",
        {
            "evaluation_passed": True,
            "safety_passed": True,
            "search_constraints": {"iterations": 0},
        },
    )
    assert decision.candidate_id == "candidate-1"
    assert decision.approved is False
    assert decision.reason == "invalid_search_constraints"
