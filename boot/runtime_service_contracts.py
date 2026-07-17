from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from runtime.constructor_tokens import is_valid_runtime_construction_token
from runtime.sealed_types import SealedType

CANON_BOOT_RUNTIME_SERVICE_CONTRACTS = True
CANON_RUNTIME_DECISION_CORE_ALIAS_REMOVED = True
CANON_RUNTIME_DECISION_CORE_COMPAT_TRIPWIRE = True
CANON_RUNTIME_EXECUTION_SERVICE_ENVELOPE_ONLY = True


def _payload(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)

    decision = getattr(value, "decision", None)
    if decision is not None:
        payload = getattr(decision, "payload", None)
        if isinstance(payload, Mapping):
            body = dict(payload)
            body.setdefault(
                "action_type",
                str(getattr(decision, "action", "") or ""),
            )
            return body

    payload = getattr(value, "payload", None)
    if isinstance(payload, Mapping):
        body = dict(payload)
        body.setdefault(
            "action_type",
            str(getattr(value, "action_type", "") or ""),
        )
        return body
    return {}


def _max_allowed_risk(action: object) -> float:
    body = _payload(action)
    raw = body.get(
        "max_allowed_risk_score",
        body.get("risk_threshold", 0.80),
    )
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 0.80
    return min(1.0, max(0.0, value))


def _validate_execution_envelope(envelope: object) -> None:
    decision = getattr(envelope, "decision", None)
    if decision is None:
        raise TypeError("canonical DecisionEnvelope required")
    if not str(getattr(decision, "decision_id", "") or "").strip():
        raise TypeError("DecisionEnvelope decision_id required")
    if not str(
        getattr(decision, "correlation_id", "") or ""
    ).strip():
        raise TypeError("DecisionEnvelope correlation_id required")
    if not str(getattr(decision, "action", "") or "").strip():
        raise TypeError("DecisionEnvelope action required")


@dataclass
class ActionExecutor(SealedType):
    _construction_token: object = field(repr=False)

    def __post_init__(self) -> None:
        if not is_valid_runtime_construction_token(self._construction_token):
            raise RuntimeError(
                "Illegal ActionExecutor construction. "
                "Use canonical boot factory path."
            )

    def execute(self, action: object) -> dict:
        return {
            "status": "accepted",
            "action_type": type(action).__name__,
        }


@dataclass
class RuntimeDecisionExecutionService(SealedType):
    """Runtime-owned governed execution for issued envelopes only.

    This service cannot issue, optimize, price, select, or transform a
    recommendation. It receives one canonical DecisionEnvelope, evaluates it
    through the governance chain, and delegates execution to the action owner.
    """

    governance_chain: object
    action_executor: object
    _construction_token: object = field(repr=False)

    def __post_init__(self) -> None:
        if not is_valid_runtime_construction_token(self._construction_token):
            raise RuntimeError(
                "Illegal runtime decision execution service construction. "
                "Use canonical boot factory path."
            )

    def execute(self, envelope: object) -> dict:
        _validate_execution_envelope(envelope)
        allowed = self.governance_chain.evaluate(envelope)
        decision = envelope.decision
        if not allowed:
            return {
                "status": "blocked",
                "reason": "governance_rejected",
                "decision_id": str(decision.decision_id),
                "action": str(decision.action),
            }
        return self.action_executor.execute(envelope)

    def execute_action(self, envelope: object) -> dict:
        """Historical execution name with envelope-only semantics."""

        return self.execute(envelope)


class RuntimeDecisionCore(SealedType):
    """Compatibility tripwire, not an alias and not an executable service.

    Historical imports of ``RuntimeDecisionCore`` must fail closed instead of
    silently resolving to ``RuntimeDecisionExecutionService``. The only
    sovereign decision issuer remains ``core.ai.decision_core.DecisionCore``.
    """

    CANON_RUNTIME_DECISION_CORE_COMPAT_TRIPWIRE = True

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError(
            "RuntimeDecisionCore compatibility alias is removed. "
            "Use core.ai.decision_core.DecisionCore for sovereign issuance or "
            "RuntimeDecisionExecutionService for governed runtime execution."
        )


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
            raise RuntimeError(
                "Illegal GovernanceChain construction. "
                "Use canonical boot factory path."
            )

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
    "CANON_RUNTIME_DECISION_CORE_ALIAS_REMOVED",
    "CANON_RUNTIME_DECISION_CORE_COMPAT_TRIPWIRE",
    "CANON_RUNTIME_EXECUTION_SERVICE_ENVELOPE_ONLY",
    "GovernanceChain",
    "RuntimeDecisionCore",
    "RuntimeDecisionExecutionService",
]
