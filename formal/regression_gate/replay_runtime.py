from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Mapping

from boot.factories.decision_core_factory import build_runtime_decision_execution_service


class _ReplayGovernance:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.calls: list[object] = []

    def evaluate(self, envelope: object) -> bool:
        self.calls.append(envelope)
        return self.allowed


class _ReplayExecutor:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def execute(self, envelope: object) -> dict[str, Any]:
        self.calls.append(envelope)
        return {
            "status": "executed",
            "action_type": str(envelope.decision.action),
            "reason": None,
            "trace": {
                "route": "DecisionCore->RuntimeExecutor",
                "guard_passed": True,
                "status": "executed",
            },
        }


def replay_runtime_decision(payload: Mapping[str, Any]) -> dict[str, Any]:
    action_name = str(payload.get("action_type", "ReplayAction"))
    governance = _ReplayGovernance(bool(payload.get("allowed", False)))
    executor = _ReplayExecutor()
    execution_service = build_runtime_decision_execution_service(
        governance_chain=governance,
        action_executor=executor,
    )
    envelope = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id=str(payload.get("decision_id") or "formal-replay-decision"),
            correlation_id=str(payload.get("correlation_id") or "formal-replay-correlation"),
            action=action_name,
            payload=dict(payload),
        )
    )
    result = dict(execution_service.execute(envelope))
    result.pop("action", None)
    result.setdefault("action_type", action_name)
    if result.get("status") == "blocked":
        result["reason"] = "governance_rejected"
        result["trace"] = {
            "route": "DecisionCore->RuntimeExecutor",
            "guard_passed": False,
            "status": "blocked",
        }
    return result
