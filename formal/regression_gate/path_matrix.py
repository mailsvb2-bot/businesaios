from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from boot.factories.decision_core_factory import build_runtime_decision_execution_service


@dataclass(frozen=True)
class RuntimePathCase:
    name: str
    governance_allowed: bool
    action: object
    expected_status: str
    expected_executor_calls: int


class _GovernanceStub:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.calls: list[object] = []

    def evaluate(self, envelope: object) -> bool:
        self.calls.append(envelope)
        return self.allowed


class _ExecutorStub:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def execute(self, envelope: object) -> dict[str, Any]:
        self.calls.append(envelope)
        decision = envelope.decision
        return {
            "status": "executed",
            "action_type": str(decision.action),
            "call_count": len(self.calls),
        }


def _envelope_for(case: RuntimePathCase) -> object:
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id=f"formal:{case.name}",
            correlation_id=f"formal-correlation:{case.name}",
            action=type(case.action).__name__,
            payload={"formal_case": case.name},
        )
    )


def run_runtime_path_case(case: RuntimePathCase) -> dict[str, Any]:
    governance = _GovernanceStub(case.governance_allowed)
    executor = _ExecutorStub()
    execution_service = build_runtime_decision_execution_service(
        governance_chain=governance,
        action_executor=executor,
    )
    result = execution_service.execute(_envelope_for(case))
    return {
        "case": case.name,
        "result": result,
        "governance_calls": len(governance.calls),
        "executor_calls": len(executor.calls),
    }
