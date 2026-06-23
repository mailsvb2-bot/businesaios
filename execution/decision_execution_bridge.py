from typing import Protocol

from contracts.action_result import ActionResult
from kernel.decision_result import DecisionResult


class ExecutionRunPort(Protocol):
    def run(self, action: object) -> ActionResult: ...


class DecisionToExecutionFlow:
    def run(self, decision_result: DecisionResult, execution_pipeline: ExecutionRunPort) -> ActionResult:
        action = decision_result.executable_action
        if action is None:
            trace = decision_result.trace
            decision_id = '' if trace is None else str(trace.decision_id)
            return ActionResult(
                action_id=decision_id.replace('decision_', 'action_'),
                status='skipped',
                message='no_executable_action',
                payload={'approved': False},
            )
        return execution_pipeline.run(action)
