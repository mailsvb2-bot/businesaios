from __future__ import annotations

import importlib

import pytest

from runtime.platform.support.optimization.self_optimization_loop import SelfOptimizationLoop
from runtime.platform.support.optimization.service import OptimizationDecisionService


def test_optimization_packages_now_resolve_to_real_files() -> None:
    module_names = [
        'runtime.platform.support.optimization.gates.promotion_gate',
        'runtime.platform.support.optimization.gates.rollback_gate',
        'runtime.platform.support.optimization.search.architecture_search',
        'runtime.platform.support.optimization.search.scheduler_search',
    ]
    for module_name in module_names:
        module = importlib.import_module(module_name)
        assert getattr(module, '__file__', '').endswith('.py')


def test_optimization_decision_service_normalizes_candidate_id_and_payload() -> None:
    service = OptimizationDecisionService()
    decision = service.decide_promotion(' candidate-1 ', {'evaluation_passed': True, 'safety_passed': True})
    assert decision.candidate_id == 'candidate-1'
    assert decision.approved is True

    with pytest.raises(ValueError):
        service.decide_promotion('   ', {'evaluation_passed': True})

    with pytest.raises(TypeError):
        service.decide_rollback('candidate-1', ['not-a-dict'])


def test_self_optimization_loop_preserves_normalized_candidate_id() -> None:
    result = SelfOptimizationLoop().run(' candidate-7 ', {'evaluation_passed': True, 'safety_passed': True})
    assert result.candidate_id == 'candidate-7'
    assert result.accepted is True
