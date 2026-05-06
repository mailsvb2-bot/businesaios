from __future__ import annotations
from contracts.action_result import ActionResult
from contracts.executable_action import ExecutableAction
from shared.registry import ActionRunnerRegistry
from execution.effectors.result import EffectorResult


class ActionRunner:
    def __init__(self, registry: ActionRunnerRegistry) -> None:
        self._registry = registry

    def run(self, action: ExecutableAction) -> ActionResult:
        runner = self._registry.get(action.action_type)
        result = runner.run(action)
        if isinstance(result, ActionResult):
            return result
        if isinstance(result, EffectorResult):
            return result.to_action_result(action_id=action.action_id, action_type=action.action_type)
        if isinstance(result, dict):
            return ActionResult(
                action_id=action.action_id,
                status=str(result.get('status', 'unknown')),
                message=str(result.get('message', '')),
                payload=dict(result.get('payload', result)),
            )
        raise TypeError(f'runner for {action.action_type} returned unsupported result type: {type(result)!r}')
