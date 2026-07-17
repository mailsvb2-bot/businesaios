from __future__ import annotations

from dataclasses import dataclass

import pytest

from core.ai import (
    _reset_decision_core_singleton_for_tests,
    set_decision_core_singleton,
)
from runtime.decision_path_lock import (
    DecisionPathLockError,
    issue_locked_decision,
    lock_decision_for_executor,
    lock_world_state,
    resolve_decision_issue_callable,
)


@pytest.fixture(autouse=True)
def _isolated_decision_core_singleton():
    _reset_decision_core_singleton_for_tests()
    try:
        yield
    finally:
        _reset_decision_core_singleton_for_tests()


@dataclass
class _Decision:
    decision_id: str
    correlation_id: str


@dataclass
class _Envelope:
    decision: _Decision


class _IssueOnlyCore:
    def issue(self, state):
        del state
        return _Envelope(
            decision=_Decision(decision_id="d-1", correlation_id="c-1")
        )


class _OptimizeOnlyCore:
    def optimize(self, state):
        return state


def test_lock_world_state_rejects_none_and_envelope_like_payload() -> None:
    with pytest.raises(DecisionPathLockError):
        lock_world_state(state=None)

    with pytest.raises(DecisionPathLockError):
        lock_world_state(
            state=_Envelope(
                decision=_Decision(decision_id="d", correlation_id="c")
            )
        )


def test_resolve_decision_issue_callable_requires_registered_issue_owner() -> None:
    core = _IssueOnlyCore()
    set_decision_core_singleton(core)

    callable_ = resolve_decision_issue_callable(core)

    assert callable_(state={"x": 1}).decision.decision_id == "d-1"


def test_resolve_decision_issue_callable_rejects_optimize_only_owner() -> None:
    core = _OptimizeOnlyCore()
    set_decision_core_singleton(core)

    with pytest.raises(DecisionPathLockError):
        resolve_decision_issue_callable(core)


def test_issue_locked_decision_routes_world_state_to_registered_issue() -> None:
    core = _IssueOnlyCore()
    set_decision_core_singleton(core)

    locked = issue_locked_decision(
        decision_core=core,
        state={"goal": "grow"},
    )

    assert locked.stage == "decision_core"
    assert locked.state == {"goal": "grow"}
    assert locked.envelope.decision.correlation_id == "c-1"


def test_lock_decision_for_executor_requires_canonical_envelope_shape() -> None:
    locked = lock_decision_for_executor(
        envelope=_Envelope(
            decision=_Decision(decision_id="d-2", correlation_id="c-2")
        )
    )
    assert locked.stage == "executor"

    with pytest.raises(DecisionPathLockError):
        lock_decision_for_executor(envelope=object())
