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


def test_resolve_headless_decision_callable_accepts_explicit_issue_owner() -> None:
    core = _IssueOnlyCore()

    callable_ = resolve_headless_decision_callable(core)

    assert callable_({"x": 2}).decision.decision_id == "d-1"


def test_resolve_headless_decision_callable_accepts_explicit_optimize_alias() -> None:
    core = _OptimizeOnlyCore()

    callable_ = resolve_headless_decision_callable(core)

    envelope = callable_({"x": 3})
    assert envelope.decision.decision_id == "d-2"
    assert envelope.state == {"x": 3}


def test_issue_headless_decision_routes_through_explicit_runtime_owner() -> None:
    core = _IssueOnlyCore()

    envelope = issue_headless_decision(
        decision_core=core,
        state={"goal": "grow"},
    )

    assert envelope.decision.correlation_id == "c-1"
    assert envelope.state == {"goal": "grow"}


def test_issue_headless_decision_fails_closed_for_invalid_explicit_owner() -> None:
    with pytest.raises(
        HeadlessDecisionGatewayContractError,
        match=r"decision_core must provide callable issue\(\) or optimize\(\)",
    ):
        issue_headless_decision(decision_core=_EmptyCore(), state={})


def test_issue_headless_decision_ignores_unrelated_boot_singleton() -> None:
    boot_registered = _IssueOnlyCore()
    explicit = _OptimizeOnlyCore()
    set_decision_core_singleton(boot_registered)

    envelope = issue_headless_decision(
        decision_core=explicit,
        state={"goal": "grow"},
    )

    assert envelope.decision.decision_id == "d-2"
    assert envelope.state == {"goal": "grow"}
