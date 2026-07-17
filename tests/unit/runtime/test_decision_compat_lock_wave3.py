from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.application._ports_impl import DecisionExecutionPort
from runtime.application.decision_transition_lock import (
    DecisionTransitionLockError,
    execute_locked_transition_action,
    resolve_transition_execute_callable,
    validate_no_raw_decision_helpers,
)


class _ExecutionOwner:
    def __init__(self) -> None:
        self.envelopes: list[object] = []

    def execute(self, envelope: object) -> dict[str, object]:
        self.envelopes.append(envelope)
        return {"ok": True, "envelope": envelope}


class _BadAdapter:
    def issue(self, state: object) -> object:
        return state


class _CombinedOwner:
    def decide_and_execute(self, action: object) -> object:
        return action


class _MissingExecutionOwner:
    pass


def _envelope(*, action: str = "demo@v1"):
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
            action=action,
        )
    )


def test_execute_locked_transition_action_uses_execution_owner() -> None:
    owner = _ExecutionOwner()
    envelope = _envelope()

    result = execute_locked_transition_action(
        owner=owner,
        action=envelope,
    )

    assert result["ok"] is True
    assert owner.envelopes == [envelope]


def test_execute_locked_transition_action_rejects_raw_action() -> None:
    with pytest.raises(
        DecisionTransitionLockError,
        match="canonical_decision_envelope_required",
    ):
        execute_locked_transition_action(
            owner=_ExecutionOwner(),
            action={"kind": "demo"},
        )


def test_resolve_transition_execute_callable_fails_closed_without_execute() -> None:
    with pytest.raises(DecisionTransitionLockError):
        resolve_transition_execute_callable(_MissingExecutionOwner())


def test_validate_no_raw_decision_helpers_rejects_adapter_with_issue_method() -> None:
    with pytest.raises(DecisionTransitionLockError):
        validate_no_raw_decision_helpers(_BadAdapter())


def test_combined_decision_execution_owner_is_rejected() -> None:
    with pytest.raises(
        DecisionTransitionLockError,
        match="decide_and_execute",
    ):
        validate_no_raw_decision_helpers(_CombinedOwner())


def test_runtime_application_port_delegates_envelope_via_lock() -> None:
    owner = _ExecutionOwner()
    port = DecisionExecutionPort(decision_core=owner)
    envelope = _envelope(action="x@v1")

    result = port.execute_action(envelope)

    assert result["ok"] is True
    assert owner.envelopes == [envelope]
