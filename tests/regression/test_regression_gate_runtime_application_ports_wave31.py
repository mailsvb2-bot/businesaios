from __future__ import annotations

from runtime.application.action_dispatcher import ActionDispatcher
from runtime.domain_ports import DecisionExecutionPort


class _DecisionCoreStub:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def decide_and_execute(self, action: object) -> dict:
        self.calls.append(action)
        return {"status": "executed", "action_type": type(action).__name__}


class _Action:
    pass



def test_application_and_domain_ports_preserve_single_decision_flow() -> None:
    core = _DecisionCoreStub()
    port = DecisionExecutionPort(decision_core=core)
    dispatcher = ActionDispatcher(decision_execution_port=port)
    result = dispatcher.dispatch(_Action())
    assert result["status"] == "executed"
    assert len(core.calls) == 1
