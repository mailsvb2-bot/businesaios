from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from boot.factories.decision_core_factory import build_decision_core


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

    def evaluate(self, action: object) -> bool:
        self.calls.append(action)
        return self.allowed


class _ExecutorStub:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def execute(self, action: object) -> dict[str, Any]:
        self.calls.append(action)
        return {"status": "executed", "action_type": type(action).__name__, "call_count": len(self.calls)}


def run_runtime_path_case(case: RuntimePathCase) -> dict[str, Any]:
    governance = _GovernanceStub(case.governance_allowed)
    executor = _ExecutorStub()
    core = build_decision_core(governance_chain=governance, action_executor=executor)
    result = core.decide_and_execute(case.action)
    return {
        "case": case.name,
        "result": result,
        "governance_calls": len(governance.calls),
        "executor_calls": len(executor.calls),
    }
