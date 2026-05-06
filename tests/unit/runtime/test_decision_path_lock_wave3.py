from __future__ import annotations

from dataclasses import dataclass

import pytest

from runtime.decision_path_lock import (
    DecisionPathLockError,
    issue_locked_decision,
    lock_decision_for_executor,
    lock_world_state,
    resolve_decision_issue_callable,
)


@dataclass
class _Decision:
    decision_id: str
    correlation_id: str


@dataclass
class _Envelope:
    decision: _Decision


class _IssueOnlyCore:
    def issue(self, state):
        return _Envelope(decision=_Decision(decision_id='d-1', correlation_id='c-1'))


class _OptimizeOnlyCore:
    def optimize(self, state):
        return state


def test_lock_world_state_rejects_none_and_envelope_like_payload() -> None:
    with pytest.raises(DecisionPathLockError):
        lock_world_state(state=None)

    with pytest.raises(DecisionPathLockError):
        lock_world_state(state=_Envelope(decision=_Decision(decision_id='d', correlation_id='c')))


def test_resolve_decision_issue_callable_requires_issue_owner() -> None:
    callable_ = resolve_decision_issue_callable(_IssueOnlyCore())
    assert callable_(state={'x': 1}).decision.decision_id == 'd-1'

    with pytest.raises(DecisionPathLockError):
        resolve_decision_issue_callable(_OptimizeOnlyCore())


def test_issue_locked_decision_routes_world_state_to_issue() -> None:
    locked = issue_locked_decision(decision_core=_IssueOnlyCore(), state={'goal': 'grow'})
    assert locked.stage == 'decision_core'
    assert locked.state == {'goal': 'grow'}
    assert locked.envelope.decision.correlation_id == 'c-1'


def test_lock_decision_for_executor_requires_canonical_envelope_shape() -> None:
    locked = lock_decision_for_executor(envelope=_Envelope(decision=_Decision(decision_id='d-2', correlation_id='c-2')))
    assert locked.stage == 'executor'

    with pytest.raises(DecisionPathLockError):
        lock_decision_for_executor(envelope=object())
