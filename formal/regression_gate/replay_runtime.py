from __future__ import annotations

from typing import Any, Mapping

from boot.factories.decision_core_factory import build_decision_core


class _ReplayGovernance:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.calls: list[object] = []

    def evaluate(self, action: object) -> bool:
        self.calls.append(action)
        return self.allowed


class _ReplayExecutor:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def execute(self, action: object) -> dict[str, Any]:
        self.calls.append(action)
        return {
            "status": "executed",
            "action_type": type(action).__name__,
            "reason": None,
            "trace": {
                "route": "DecisionCore->RuntimeExecutor",
                "guard_passed": True,
                "status": "executed",
            },
        }


class _ReplayAction:
    pass



def replay_runtime_decision(payload: Mapping[str, Any]) -> dict[str, Any]:
    action_name = str(payload.get("action_type", "ReplayAction"))
    action_type = type(action_name, (_ReplayAction,), {})
    action = action_type()
    governance = _ReplayGovernance(bool(payload.get("allowed", False)))
    executor = _ReplayExecutor()
    core = build_decision_core(governance_chain=governance, action_executor=executor)
    result = dict(core.decide_and_execute(action))
    result.setdefault("action_type", action_name)
    if result.get("status") == "blocked":
        result["reason"] = "governance_rejected"
        result["trace"] = {
            "route": "DecisionCore->RuntimeExecutor",
            "guard_passed": False,
            "status": "blocked",
        }
    return result
