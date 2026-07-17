from __future__ import annotations

import pytest

from core.ai import (
    _reset_decision_core_singleton_for_tests,
    set_decision_core_singleton,
)
from execution.capability_aware_planning import CapabilityAwarePlanner
from execution.capability_health_registry import CapabilityHealthRegistry
from execution.capability_matrix import CapabilityMatrix
from execution.capability_router import ExecutionCapabilityRouter
from execution.headless_contract import HeadlessExecutionContract


@pytest.fixture(autouse=True)
def _isolated_decision_core_singleton():
    _reset_decision_core_singleton_for_tests()
    try:
        yield
    finally:
        _reset_decision_core_singleton_for_tests()


class _DecisionCore:
    def issue(self, state):
        raise AssertionError(f"not issued: {state!r}")


class _Executor:
    def execute(self, action):
        raise AssertionError(f"not executed: {action!r}")


class _Mapper:
    def to_world_state(self, request):
        del request
        return {}


def test_headless_contract_rebinds_capability_owner_path_to_single_router() -> None:
    matrix_a = CapabilityMatrix()
    matrix_b = CapabilityMatrix()
    registry_a = CapabilityHealthRegistry(matrix=matrix_a)
    registry_b = CapabilityHealthRegistry(matrix=matrix_b)
    router_a = ExecutionCapabilityRouter(
        matrix=matrix_a,
        health_registry=registry_a,
    )
    planner_b = CapabilityAwarePlanner(
        router=ExecutionCapabilityRouter(
            matrix=matrix_b,
            health_registry=registry_b,
        )
    )
    decision_core = _DecisionCore()
    set_decision_core_singleton(decision_core)

    contract = HeadlessExecutionContract(
        decision_core=decision_core,
        executor=_Executor(),
        state_mapper=_Mapper(),
        execution_capability_router=router_a,
        capability_aware_planner=planner_b,
        capability_matrix=matrix_a,
        capability_health_registry=registry_a,
    )

    assert contract._capability_matrix is matrix_a
    assert contract._capability_health_registry is registry_a
    assert contract._execution_capability_router is router_a
    assert (
        getattr(contract._capability_aware_planner, "_router", None)
        is contract._execution_capability_router
    )
