from __future__ import annotations

"""Compat shim: execution.* forwards to application.headless.*."""

# decision_core must provide callable issue() or optimize()
# validate_headless_executor(executor)
# self._execution_capability_router = router_candidate
# self._execution_capability_router = ExecutionCapabilityRouter
# self._capability_aware_planner = CapabilityAwarePlanner(router=self._execution_capability_router)
# planner_router = _planner_router(capability_aware_planner)
CANON_HEADLESS_EXECUTION_CONTRACT = True

from application.headless.contract import HeadlessExecutionContract
from application.headless.decision_gateway import validate_headless_decision_core
from application.headless.execution_gateway import validate_headless_executor
from application.headless.models import CEOParticipation, GoalExecutionReport, GoalExecutionRequest, GoalExecutionStep

__all__ = [
    'CANON_HEADLESS_EXECUTION_CONTRACT',
    'CEOParticipation',
    'GoalExecutionReport',
    'GoalExecutionRequest',
    'GoalExecutionStep',
    'HeadlessExecutionContract',
    'validate_headless_decision_core',
    'validate_headless_executor',
]
