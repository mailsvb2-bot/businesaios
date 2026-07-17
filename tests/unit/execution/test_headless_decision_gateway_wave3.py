from __future__ import annotations

from dataclasses import dataclass

import pytest

from application.headless.decision_gateway import (
    HeadlessDecisionGatewayContractError,
    issue_headless_decision,
    resolve_headless_decision_callable,
)
from core.ai import (
    _reset_decision_core_singleton_for_tests,
    set_decision_core_singleton,
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
    state: object


@dataclass
class _IssueOnlyCore:
    def issue(self, state):
        return _Envelope(
            decision=_Decision(decision_id="d-1", correlation_id="c-1"),
            state=state,
        )


@dataclass
class _OptimizeOnlyCore:
    def optimize(self, state):
        return _Envelope(
            decision=_Decision(decision_id="d-2", correlation_id="c-2"),
            state=state,
        )


@dataclass
class _EmptyCore:
    pass


def test_resolve_headless_decision_callable_accepts_registered_issue_owner() -> None:
    core = _IssueOnlyCore()
    set_decision_core_singleton(core)

    callable_ = resolve_headless_decision_callable(core)

    assert callable_({"x": 2}).decision.decision_id == "d-1"


def test_resolve_headless_decision_callable_rejects_optimize_only_owner() -> None:
    core = _OptimizeOnlyCore()
    set_decision_core_singleton(core)

    with pytest.raises(
        HeadlessDecisionGatewayContractError,
        match="issuer_issue_missing",
    ):
        resolve_headless_decision_callable(core)


def test_issue_headless_decision_routes_through_registered_runtime_owner() -> None:
    core = _IssueOnlyCore()
    set_decision_core_singleton(core)

    envelope = issue_headless_decision(
        decision_core=core,
        state={"goal": "grow"},
    )

    assert envelope.decision.correlation_id == "c-1"
    assert envelope.state == {"goal": "grow"}


def test_issue_headless_decision_fails_closed_without_registered_owner() -> None:
    with pytest.raises(
        HeadlessDecisionGatewayContractError,
        match="canonical_decision_core_not_initialized",
    ):
        issue_headless_decision(decision_core=_EmptyCore(), state={})


def test_issue_headless_decision_rejects_noncanonical_optimize_only_core() -> None:
    core = _OptimizeOnlyCore()
    set_decision_core_singleton(core)

    with pytest.raises(HeadlessDecisionGatewayContractError):
        issue_headless_decision(decision_core=core, state={"goal": "grow"})
