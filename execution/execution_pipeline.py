from __future__ import annotations

from typing import Protocol

from contracts.action_result import ActionResult
from contracts.executable_action import ExecutableAction


class ActionDispatchPort(Protocol):
    def dispatch(self, action: ExecutableAction) -> ActionResult: ...


class ExecutionPipeline:
    def __init__(self, dispatcher: ActionDispatchPort) -> None:
        self._dispatcher = dispatcher

    def run(self, action: ExecutableAction) -> ActionResult:
        return self._dispatcher.dispatch(action)
