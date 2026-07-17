from __future__ import annotations

from types import SimpleNamespace

import pytest

from application.headless.decision_gateway import (
    HeadlessDecisionGatewayContractError,
    issue_headless_decision,
    resolve_headless_decision_callable,
)
from core.ai import (
    get_decision_core_singleton,
    reset_decision_core_singleton,
    set_decision_core_singleton,
)
from runtime.decision_gateway import (
    DecisionGatewayContractError,
    issue_runtime_decision,
)
from runtime.decision_path_lock import (
    DecisionPathLockError,
    issue_locked_decision,
)


@pytest.fixture(autouse=True)
def _isolated_singleton():
    reset_decision_core_singleton()
    try:
        yield
    finally:
        reset_decision_core_singleton()


def _envelope(decision_id: str = "decision-1") -> SimpleNamespace:
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id=decision_id,
            correlation_id=f"correlation-{decision_id}",
        )
    )


class _Issuer:
    def __init__(self, result=None) -> None:
        self.result = result or _envelope()
        self.states: list[object] = []

    def issue(self, state):
        self.states.append(state)
        return self.result

    def optimize(self, state):
        return self.issue(state)


def test_locked_path_accepts_only_the_registered_issuer_identity() -> None:
    registered = _Issuer()
    alternate = _Issuer()
    set_decision_core_singleton(registered)

    locked = issue_locked_decision(
        decision_core=registered,
        state={"state": "ok"},
    )
    assert locked.envelope is registered.result
    assert registered.states == [{"state": "ok"}]

    with pytest.raises(
        DecisionPathLockError,
        match="noncanonical_decision_core",
    ):
        issue_locked_decision(
            decision_core=alternate,
            state={"state": "blocked"},
        )


def test_runtime_gateway_rejects_raw_results_instead_of_forging_proof() -> None:
    issuer = _Issuer(result="raw-result")
    set_decision_core_singleton(issuer)

    with pytest.raises(
        DecisionGatewayContractError,
        match="decision_envelope_missing_decision",
    ):
        issue_runtime_decision(
            issuer=issuer,
            state={"state": "raw"},
        )


def test_headless_api_preserves_envelope_behavior_via_runtime_gateway() -> None:
    issuer = _Issuer(result=_envelope("headless"))
    set_decision_core_singleton(issuer)

    assert (
        issue_headless_decision(
            decision_core=issuer,
            state={"surface": "headless"},
        )
        is issuer.result
    )
    callable_issue = resolve_headless_decision_callable(issuer)
    assert callable_issue({"surface": "callable"}) is issuer.result
    assert issuer.states == [
        {"surface": "headless"},
        {"surface": "callable"},
    ]


def test_headless_api_rejects_an_alternate_core() -> None:
    registered = _Issuer()
    set_decision_core_singleton(registered)

    with pytest.raises(
        HeadlessDecisionGatewayContractError,
        match="noncanonical_decision_issuer",
    ):
        issue_headless_decision(
            decision_core=_Issuer(),
            state={"surface": "blocked"},
        )


def test_singleton_registry_returns_the_exact_registered_object() -> None:
    issuer = _Issuer()
    set_decision_core_singleton(issuer)

    assert get_decision_core_singleton() is issuer
    set_decision_core_singleton(issuer)
    assert get_decision_core_singleton() is issuer
