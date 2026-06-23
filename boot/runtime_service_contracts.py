from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from runtime.constructor_tokens import is_valid_runtime_construction_token
from runtime.sealed_types import SealedType

CANON_BOOT_RUNTIME_SERVICE_CONTRACTS = True


def _payload(action: object) -> dict[str, Any]:
    if isinstance(action, Mapping):
        return dict(action)
    payload = getattr(action, "payload", None)
    if isinstance(payload, Mapping):
        body = dict(payload)
        body.setdefault("action_type", str(getattr(action, "action_type", "") or ""))
        return body
    return {}


def _max_allowed_risk(action: object) -> float:
    body = _payload(action)
    raw = body.get("max_allowed_risk_score", body.get("risk_threshold", 0.80))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 0.80
    return min(1.0, max(0.0, value))


@dataclass
class ActionExecutor(SealedType):
    _construction_token: object = field(repr=False)

    def __post_init__(self) -> None:
        if not is_valid_runtime_construction_token(self._construction_token):
            raise RuntimeError("Illegal ActionExecutor construction. Use canonical boot factory path.")

    def execute(self, action: object) -> dict:
        return {"status": "accepted", "action_type": type(action).__name__}


@dataclass
class RuntimeDecisionExecutionService(SealedType):
    """Runtime-owned governed action execution service.

    This is not the sovereign core.ai.decision_core.DecisionCore.
    """

    governance_chain: object
    action_executor: object
    _construction_token: object = field(repr=False)

    def __post_init__(self) -> None:
        if not is_valid_runtime_construction_token(self._construction_token):
            raise RuntimeError("Illegal runtime decision execution service construction. Use canonical boot factory path.")

    def decide_and_execute(self, action: object) -> dict:
        allowed = self.governance_chain.evaluate(action)
        if not allowed:
            return {
                "status": "blocked",
                "reason": "governance_rejected",
                "action_type": type(action).__name__,
            }
        return self.action_executor.execute(action)


RuntimeDecisionCore = RuntimeDecisionExecutionService


@dataclass
class GovernanceChain(SealedType):
    risk_engine: object
    reward_guard: object
    simulation_gate: object
    kill_switch: object
    action_budget: object
    _construction_token: object = field(repr=False)

    def __post_init__(self) -> None:
        if not is_valid_runtime_construction_token(self._construction_token):
            raise RuntimeError("Illegal GovernanceChain construction. Use canonical boot factory path.")

    def evaluate(self, action: object) -> bool:
        if not self.kill_switch.allow():
            return False
        if not self.reward_guard.validate(action):
            return False
        if not self.simulation_gate.allow(action):
            return False
        if not self.action_budget.allow(action):
            return False
        if self.risk_engine.score(action) > _max_allowed_risk(action):
            return False
        return True


__all__ = [
    "ActionExecutor",
    "CANON_BOOT_RUNTIME_SERVICE_CONTRACTS",
    "GovernanceChain",
    "RuntimeDecisionCore",
    "RuntimeDecisionExecutionService",
]
