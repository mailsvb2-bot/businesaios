from __future__ import annotations

from execution.capability_aware_planning import CapabilityAwarePlanner
from execution.capability_health_registry import CapabilityHealthRegistry
from execution.capability_matrix import CapabilityMatrix
from execution.capability_router import ExecutionCapabilityRouter
from execution.headless_contract import HeadlessExecutionContract


class _DecisionCore:
    def optimize(self, state):
        return object()


class _Executor:
    def execute(self, action):
        raise AssertionError('not executed')


class _Mapper:
    def to_world_state(self, request):
        return {}


def test_headless_contract_rebinds_capability_owner_path_to_single_router() -> None:
    matrix_a = CapabilityMatrix()
    matrix_b = CapabilityMatrix()
    registry_a = CapabilityHealthRegistry(matrix=matrix_a)
    registry_b = CapabilityHealthRegistry(matrix=matrix_b)
    router_a = ExecutionCapabilityRouter(matrix=matrix_a, health_registry=registry_a)
    planner_b = CapabilityAwarePlanner(router=ExecutionCapabilityRouter(matrix=matrix_b, health_registry=registry_b))

    contract = HeadlessExecutionContract(
        decision_core=_DecisionCore(),
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
    assert getattr(contract._capability_aware_planner, '_router', None) is contract._execution_capability_router
