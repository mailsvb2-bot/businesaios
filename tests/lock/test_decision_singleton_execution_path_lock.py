from __future__ import annotations

from types import SimpleNamespace

import pytest

from application.headless.decision_gateway import (
    issue_headless_decision,
    resolve_headless_decision_callable,
)
from core.ai import (
    _reset_decision_core_singleton_for_tests,
    get_decision_core_singleton,
    set_decision_core_singleton,
)
from runtime.decision_gateway import (
    DecisionGatewayContractError,
    issue_runtime_decision,
)
from runtime.decision_path_lock import issue_locked_decision


@pytest.fixture(autouse=True)
def _isolated_singleton():
    _reset_decision_core_singleton_for_tests()
    try:
        yield
    finally:
        _reset_decision_core_singleton_for_tests()


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


def test_locked_path_uses_the_explicit_issuer_not_global_identity() -> None:
    registered = _Issuer()
    explicit = _Issuer(result=_envelope("explicit"))
    set_decision_core_singleton(registered)

    locked = issue_locked_decision(
        decision_core=explicit,
        state={"state": "explicit"},
    )

    assert locked.envelope is explicit.result
    assert explicit.states == [{"state": "explicit"}]
    assert registered.states == []
    assert get_decision_core_singleton() is registered


def test_runtime_gateway_rejects_raw_results_instead_of_forging_proof() -> None:
    issuer = _Issuer(result="raw-result")
    set_decision_core_singleton(_Issuer())

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


def test_headless_api_does_not_replace_explicit_core_with_global_singleton() -> None:
    registered = _Issuer()
    explicit = _Issuer(result=_envelope("explicit-headless"))
    set_decision_core_singleton(registered)

    observed = issue_headless_decision(
        decision_core=explicit,
        state={"surface": "explicit"},
    )

    assert observed is explicit.result
    assert explicit.states == [{"surface": "explicit"}]
    assert registered.states == []


def test_singleton_registry_remains_a_boot_identity_guard() -> None:
    issuer = _Issuer()
    set_decision_core_singleton(issuer)

    assert get_decision_core_singleton() is issuer
    set_decision_core_singleton(issuer)
    assert get_decision_core_singleton() is issuer
