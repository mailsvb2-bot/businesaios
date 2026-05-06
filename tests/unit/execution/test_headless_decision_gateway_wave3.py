from __future__ import annotations

from dataclasses import dataclass

import pytest

from application.headless.decision_gateway import (
    HeadlessDecisionGatewayContractError,
    issue_headless_decision,
    resolve_headless_decision_callable,
)


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
        return _Envelope(decision=_Decision(decision_id='d-1', correlation_id='c-1'), state=state)




@dataclass
class _OptimizeOnlyCore:
    def optimize(self, state):
        return _Envelope(decision=_Decision(decision_id='d-2', correlation_id='c-2'), state=state)

@dataclass
class _EmptyCore:
    pass


def test_resolve_headless_decision_callable_accepts_issue_or_optimize() -> None:
    callable_ = resolve_headless_decision_callable(_IssueOnlyCore())
    assert callable_({'x': 2}).decision.decision_id == 'd-1'

    optimize_callable = resolve_headless_decision_callable(_OptimizeOnlyCore())
    assert optimize_callable({'x': 3}).decision.decision_id == 'd-2'

    with pytest.raises(HeadlessDecisionGatewayContractError):
        resolve_headless_decision_callable(object())


def test_issue_headless_decision_routes_through_gateway_owner() -> None:
    envelope = issue_headless_decision(decision_core=_IssueOnlyCore(), state={'goal': 'grow'})
    assert envelope.decision.correlation_id == 'c-1'
    assert envelope.state == {'goal': 'grow'}


def test_issue_headless_decision_fails_closed_without_callable_surface() -> None:
    with pytest.raises(HeadlessDecisionGatewayContractError):
        issue_headless_decision(decision_core=_EmptyCore(), state={})


def test_issue_headless_decision_accepts_optimize_only_core() -> None:
    envelope = issue_headless_decision(decision_core=_OptimizeOnlyCore(), state={'goal': 'grow'})
    assert envelope.decision.correlation_id == 'c-2'
    assert envelope.state == {'goal': 'grow'}
