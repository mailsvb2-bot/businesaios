from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.actions import ACTION_EXECUTE_PLAN_V1
from runtime.ceo import execute_strategy


class _ExecutionOwner:
    def __init__(self) -> None:
        self.envelopes = []

    def execute(self, envelope):
        self.envelopes.append(envelope)
        return {"ok": True, "envelope": envelope}


class _AuditLog:
    def event_names(self):
        return ("ceo.started",)


class _Observability:
    def __init__(self) -> None:
        self.audit_log = _AuditLog()


def _issued_envelope(*, user_id: str):
    payload = {"user_id": user_id, "steps": []}
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
            action=ACTION_EXECUTE_PLAN_V1,
            payload=payload,
        )
    )


def test_execute_strategy_routes_matching_envelope_through_execution_owner() -> None:
    plan = type("Plan", (), {"steps": []})()
    owner = _ExecutionOwner()
    envelope = _issued_envelope(user_id="u-1")

    result = execute_strategy(
        plan,
        user_id="u-1",
        decision_core=owner,
        observability=_Observability(),
        decision_envelope=envelope,
    )

    assert result["ok"] is True
    assert owner.envelopes == [envelope]


def test_execute_strategy_rejects_execution_without_issued_envelope() -> None:
    plan = type("Plan", (), {"steps": []})()

    with pytest.raises(TypeError, match="decision_envelope"):
        execute_strategy(
            plan,
            user_id="u-1",
            decision_core=_ExecutionOwner(),
        )


def test_execute_strategy_rejects_envelope_payload_drift() -> None:
    plan = type("Plan", (), {"steps": []})()
    envelope = _issued_envelope(user_id="other-user")

    with pytest.raises(ValueError, match="payload does not match"):
        execute_strategy(
            plan,
            user_id="u-1",
            decision_core=_ExecutionOwner(),
            decision_envelope=envelope,
        )


def test_execute_strategy_without_execution_owner_returns_proposal() -> None:
    plan = type("Plan", (), {"steps": []})()

    proposal = execute_strategy(plan, user_id="u-2")

    assert proposal.action == ACTION_EXECUTE_PLAN_V1
    assert proposal.payload["user_id"] == "u-2"
