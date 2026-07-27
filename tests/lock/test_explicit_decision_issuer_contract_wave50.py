from __future__ import annotations

from dataclasses import dataclass

import pytest

from runtime.decision_gateway import (
    DecisionGatewayContractError,
    issue_runtime_decision,
    validate_runtime_decision_issuer,
)
from runtime.decision_path_lock import bind_decision_issuer


@dataclass(frozen=True)
class _Decision:
    decision_id: str = "decision-1"
    correlation_id: str = "correlation-1"


@dataclass(frozen=True)
class _Envelope:
    decision: _Decision = _Decision()


class _IssueOnly:
    def __init__(self) -> None:
        self.states: list[object] = []

    def issue(self, state: object) -> _Envelope:
        self.states.append(state)
        return _Envelope()


class _OptimizeOnly:
    def __init__(self) -> None:
        self.states: list[object] = []

    def optimize(self, state: object) -> _Envelope:
        self.states.append(state)
        return _Envelope()


def test_explicit_issue_and_optimize_aliases_share_one_gateway_contract() -> None:
    state = {"tenant_id": "tenant-a"}
    for issuer in (_IssueOnly(), _OptimizeOnly()):
        validate_runtime_decision_issuer(issuer)
        envelope = issue_runtime_decision(issuer=issuer, state=state)
        assert envelope.decision.decision_id == "decision-1"
        assert issuer.states == [state]


def test_missing_explicit_issuer_fails_without_global_fallback() -> None:
    with pytest.raises(DecisionGatewayContractError, match="decision_core_missing"):
        validate_runtime_decision_issuer(None)


def test_binding_prefers_issue_but_never_reads_process_singleton() -> None:
    class Both(_IssueOnly):
        def optimize(self, state: object) -> _Envelope:
            raise AssertionError("optimize must not be selected when issue exists")

    issuer = Both()
    binding = bind_decision_issuer(issuer)
    assert binding.decision_core is issuer
    assert binding.method_name == "issue"
    assert binding.invoke({"x": 1}).decision.decision_id == "decision-1"
