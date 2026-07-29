from __future__ import annotations

from types import SimpleNamespace

from runtime.application.action_dispatcher import ActionDispatcher
from runtime.domain_ports import DecisionExecutionPort


class _ExecutionOwnerStub:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def execute(self, envelope: object) -> dict:
        self.calls.append(envelope)
        return {
            "status": "executed",
            "action_type": envelope.decision.action,
        }


def _envelope():
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
            action="notify_owner@v1",
            payload={},
        )
    )


def test_application_and_domain_ports_preserve_single_decision_flow() -> None:
    owner = _ExecutionOwnerStub()
    port = DecisionExecutionPort(decision_core=owner)
    dispatcher = ActionDispatcher(decision_execution_port=port)
    envelope = _envelope()
    result = dispatcher.dispatch(envelope)
    assert result["status"] == "executed"
    assert owner.calls == [envelope]
