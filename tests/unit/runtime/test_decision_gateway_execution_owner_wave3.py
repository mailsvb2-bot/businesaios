from __future__ import annotations

from dataclasses import dataclass

import pytest

from core.ai import (
    _reset_decision_core_singleton_for_tests,
    set_decision_core_singleton,
)
from runtime.decision_gateway import (
    DecisionGatewayContractError,
    execute_runtime_decision,
)


@pytest.fixture(autouse=True)
def _isolated_decision_core_singleton():
    _reset_decision_core_singleton_for_tests()
    try:
        yield
    finally:
        _reset_decision_core_singleton_for_tests()


@dataclass
class _Decision:
    decision_id: str
    correlation_id: str


@dataclass
class _Envelope:
    decision: _Decision
    state: object


class _Issuer:
    def __init__(self) -> None:
        self.states: list[object] = []

    def issue(self, state: object) -> _Envelope:
        self.states.append(state)
        return _Envelope(
            decision=_Decision(decision_id="d-1", correlation_id="c-1"),
            state=state,
        )


class _Executor:
    def __init__(self) -> None:
        self.envelopes: list[object] = []

    def execute(self, envelope: object) -> dict[str, object]:
        self.envelopes.append(envelope)
        return {"ok": True, "envelope": envelope}


def test_execute_runtime_decision_routes_registered_issue_then_execute() -> None:
    issuer = _Issuer()
    set_decision_core_singleton(issuer)
    executor = _Executor()

    result = execute_runtime_decision(
        issuer=issuer,
        executor=executor,
        state={"x": 1},
    )

    assert issuer.states == [{"x": 1}]
    assert len(executor.envelopes) == 1
    assert executor.envelopes[0].decision.decision_id == "d-1"
    assert result["ok"] is True


def test_execute_runtime_decision_requires_executor_execute() -> None:
    issuer = _Issuer()
    set_decision_core_singleton(issuer)

    with pytest.raises(
        DecisionGatewayContractError,
        match="executor_must_provide_callable_execute",
    ):
        execute_runtime_decision(
            issuer=issuer,
            executor=object(),
            state={"x": 1},
        )
