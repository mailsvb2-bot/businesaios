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
        del state
        return _Envelope(
            decision=_Decision(decision_id="d-2", correlation_id="c-2")
        )


class _EmptyCore:
    pass


def test_lock_world_state_rejects_none_and_envelope_like_payload() -> None:
    with pytest.raises(DecisionPathLockError):
        lock_world_state(state=None)

    with pytest.raises(DecisionPathLockError):
        lock_world_state(
            state=_Envelope(
                decision=_Decision(decision_id="d", correlation_id="c")
            )
        )


def test_resolve_decision_issue_callable_accepts_explicit_issue_owner() -> None:
    core = _IssueOnlyCore()

    callable_ = resolve_decision_issue_callable(core)

    assert callable_(state={"x": 1}).decision.decision_id == "d-1"


def test_resolve_decision_issue_callable_accepts_explicit_optimize_alias() -> None:
    core = _OptimizeOnlyCore()

    callable_ = resolve_decision_issue_callable(core)

    assert callable_(state={"x": 2}).decision.decision_id == "d-2"


def test_resolve_decision_issue_callable_fails_closed_for_invalid_owner() -> None:
    with pytest.raises(
        DecisionPathLockError,
        match="decision_core_must_provide_callable_issue_or_optimize",
    ):
        resolve_decision_issue_callable(_EmptyCore())


def test_issue_locked_decision_routes_world_state_to_explicit_issuer() -> None:
    boot_registered = _IssueOnlyCore()
    explicit = _OptimizeOnlyCore()
    set_decision_core_singleton(boot_registered)

    locked = issue_locked_decision(
        decision_core=explicit,
        state={"goal": "grow"},
    )

    assert locked.stage == "decision_core"
    assert locked.state == {"goal": "grow"}
    assert locked.envelope.decision.correlation_id == "c-2"


def test_lock_decision_for_executor_requires_canonical_envelope_shape() -> None:
    locked = lock_decision_for_executor(
        envelope=_Envelope(
            decision=_Decision(decision_id="d-2", correlation_id="c-2")
        )
    )
    assert locked.stage == "executor"

    with pytest.raises(DecisionPathLockError):
        lock_decision_for_executor(envelope=object())
