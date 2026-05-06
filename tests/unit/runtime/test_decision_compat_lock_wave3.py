from __future__ import annotations

import pytest

from runtime.application.decision_transition_lock import (
    DecisionTransitionLockError,
    execute_locked_transition_action,
    resolve_transition_execute_callable,
    validate_no_raw_decision_helpers,
)
from runtime.application._ports_impl import DecisionExecutionPort


class _CompatOwner:
    def __init__(self) -> None:
        self.actions: list[object] = []

    def decide_and_execute(self, action: object) -> dict[str, object]:
        self.actions.append(action)
        return {'ok': True, 'action': action}


class _BadAdapter:
    def issue(self, state: object) -> object:
        return state


class _MissingCompatOwner:
    pass


def test_execute_locked_transition_action_uses_compat_owner() -> None:
    owner = _CompatOwner()
    result = execute_locked_transition_action(owner=owner, action={'kind': 'demo'})
    assert result['ok'] is True
    assert owner.actions == [{'kind': 'demo'}]


def test_resolve_transition_execute_callable_fails_closed_without_compat_method() -> None:
    with pytest.raises(DecisionTransitionLockError):
        resolve_transition_execute_callable(_MissingCompatOwner())


def test_validate_no_raw_decision_helpers_rejects_adapter_with_issue_method() -> None:
    with pytest.raises(DecisionTransitionLockError):
        validate_no_raw_decision_helpers(_BadAdapter())


def test_runtime_application_port_delegates_via_compat_lock() -> None:
    owner = _CompatOwner()
    port = DecisionExecutionPort(decision_core=owner)
    result = port.execute_action({'kind': 'x'})
    assert result['ok'] is True
    assert owner.actions == [{'kind': 'x'}]
