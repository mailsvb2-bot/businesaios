from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import application.headless.contract as headless_contract
import application.headless.decision_gateway as headless_gateway
import runtime.decision_gateway as gateway
import runtime.decision_path_lock as path_lock
from core.ai import (
    _reset_decision_core_singleton_for_tests,
    set_decision_core_singleton,
)


def envelope(*, decision_id: str = "decision-1", correlation_id: str = "corr-1"):
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id=decision_id,
            correlation_id=correlation_id,
            action="noop",
            payload={},
        )
    )


class OptimizeOnlyCore:
    def __init__(self, result=None):
        self.result = result or envelope()
        self.calls = []

    def optimize(self, state):
        self.calls.append(state)
        return self.result


class IssueOnlyCore:
    def __init__(self, result=None):
        self.result = result or envelope()
        self.calls = []

    def issue(self, state):
        self.calls.append(state)
        return self.result


class BothCore:
    def __init__(self):
        self.issue_calls = []
        self.optimize_calls = []

    def issue(self, state):
        self.issue_calls.append(state)
        return envelope(decision_id="issue")

    def optimize(self, state):
        self.optimize_calls.append(state)
        return envelope(decision_id="optimize")


@pytest.fixture(autouse=True)
def clear_singleton():
    _reset_decision_core_singleton_for_tests()
    yield
    _reset_decision_core_singleton_for_tests()


def test_explicit_optimize_only_issuer_reaches_execution_without_singleton():
    core = OptimizeOnlyCore()
    executor = SimpleNamespace(execute=Mock(return_value={"executed": True}))
    state = {"goal": "grow"}

    gateway.validate_runtime_decision_issuer(core)
    assert gateway._registered_decision_core(core) is core
    result = gateway.execute_runtime_decision(
        issuer=core,
        executor=executor,
        state=state,
    )

    assert result == {"executed": True}
    assert core.calls == [state]
    executor.execute.assert_called_once_with(core.result)


def test_explicit_issuer_is_not_replaced_by_initialized_global_singleton():
    poison = IssueOnlyCore()
    set_decision_core_singleton(poison)
    explicit = OptimizeOnlyCore()

    observed = gateway.issue_runtime_decision(
        issuer=explicit,
        state={"source": "explicit"},
    )

    assert observed is explicit.result
    assert explicit.calls == [{"source": "explicit"}]
    assert poison.calls == []


def test_issue_precedes_optimize_when_both_aliases_exist():
    core = BothCore()

    observed = gateway.issue_runtime_decision(issuer=core, state={"x": 1})

    assert observed.decision.decision_id == "issue"
    assert core.issue_calls == [{"x": 1}]
    assert core.optimize_calls == []


def test_callable_binding_freezes_selected_method():
    core = BothCore()
    decision_callable = gateway.build_runtime_decision_callable(issuer=core)
    original_issue = core.issue
    core.issue = None

    observed = decision_callable({"frozen": True})

    assert observed.decision.decision_id == "issue"
    assert core.issue_calls == [{"frozen": True}]
    assert core.optimize_calls == []
    assert original_issue.__self__ is core


def test_invalid_issuer_errors_are_honest_and_stable():
    with pytest.raises(
        gateway.DecisionGatewayContractError,
        match="decision_core_missing",
    ):
        gateway.validate_runtime_decision_issuer(None)

    with pytest.raises(
        gateway.DecisionGatewayContractError,
        match="decision_core_must_provide_callable_issue_or_optimize",
    ):
        gateway.validate_runtime_decision_issuer(object())

    with pytest.raises(
        headless_gateway.HeadlessDecisionGatewayContractError,
        match=r"decision_core must provide callable issue\(\) or optimize\(\)",
    ):
        headless_gateway.validate_headless_decision_core(object())


def test_headless_contract_accepts_optimize_only_and_does_not_relabel_internal_errors(monkeypatch):
    core = OptimizeOnlyCore()
    executor = SimpleNamespace(execute=lambda value: value)
    mapper = SimpleNamespace(to_world_state=lambda request: request)

    contract = headless_contract.HeadlessExecutionContract(
        decision_core=core,
        executor=executor,
        state_mapper=mapper,
    )
    assert contract._decision_core is core

    monkeypatch.setattr(
        headless_contract,
        "validate_headless_decision_core",
        Mock(side_effect=RuntimeError("internal_validator_failure")),
    )
    with pytest.raises(RuntimeError, match="internal_validator_failure"):
        headless_contract.HeadlessExecutionContract(
            decision_core=core,
            executor=executor,
            state_mapper=mapper,
        )


def test_headless_gateway_surface_delegates_to_single_runtime_owner():
    core = OptimizeOnlyCore()
    state = {"goal": "retain"}

    ingress = headless_gateway.build_headless_decision_ingress(decision_core=core)
    assert ingress.issue(state) is core.result
    assert headless_gateway.issue_headless_decision(
        decision_core=core,
        state=state,
    ) is core.result
    bound = headless_gateway.resolve_headless_decision_callable(core)
    assert bound(state) is core.result
    assert core.calls == [state, state, state]


def test_headless_gateway_translates_runtime_failures(monkeypatch):
    error = gateway.DecisionGatewayContractError("runtime_path_failed")
    monkeypatch.setattr(
        headless_gateway,
        "issue_runtime_decision",
        Mock(side_effect=error),
    )
    ingress = headless_gateway.HeadlessDecisionIngress(decision_core=object())

    with pytest.raises(
        headless_gateway.HeadlessDecisionGatewayContractError,
        match="runtime_path_failed",
    ):
        ingress.issue({})
    with pytest.raises(
        headless_gateway.HeadlessDecisionGatewayContractError,
        match="runtime_path_failed",
    ):
        headless_gateway.issue_headless_decision(
            decision_core=object(),
            state={},
        )

    monkeypatch.setattr(
        headless_gateway,
        "build_runtime_decision_callable",
        Mock(side_effect=error),
    )
    with pytest.raises(
        headless_gateway.HeadlessDecisionGatewayContractError,
        match="runtime_path_failed",
    ):
        headless_gateway.resolve_headless_decision_callable(object())

    monkeypatch.setattr(
        headless_gateway,
        "validate_runtime_decision_issuer",
        Mock(side_effect=error),
    )
    with pytest.raises(
        headless_gateway.HeadlessDecisionGatewayContractError,
        match="runtime_path_failed",
    ):
        headless_gateway.validate_headless_decision_core(object())


def test_decision_issuer_binding_contract_and_specific_method_errors():
    issue = IssueOnlyCore()
    optimize = OptimizeOnlyCore()

    issue_binding = path_lock.bind_decision_issuer(issue)
    optimize_binding = path_lock.bind_decision_issuer(optimize)
    assert issue_binding.method_name == "issue"
    assert optimize_binding.method_name == "optimize"
    assert path_lock.bind_decision_issuer(issue_binding) is issue_binding
    assert path_lock.resolve_decision_issue_callable(optimize)({}) is optimize.result

    with pytest.raises(
        path_lock.DecisionPathLockError,
        match="decision_core_must_provide_callable_optimize",
    ):
        path_lock.bind_decision_issuer(issue, method_name="optimize")

    both = BothCore()
    both_issue_binding = path_lock.bind_decision_issuer(both)
    rebound = path_lock.bind_decision_issuer(
        both_issue_binding,
        method_name="optimize",
    )
    assert rebound.method_name == "optimize"
    assert rebound.decision_core is both


def test_optimize_runtime_decision_is_explicit_and_fail_closed():
    core = OptimizeOnlyCore()
    assert gateway.optimize_runtime_decision(
        issuer=core,
        state={"x": 1},
    ) is core.result

    with pytest.raises(
        gateway.DecisionGatewayContractError,
        match="noncanonical_decision_optimize_method",
    ):
        gateway.optimize_runtime_decision(
            issuer=core,
            state={},
            method_name="decide",
        )

    with pytest.raises(
        gateway.DecisionGatewayContractError,
        match="canonical_decision_core_optimize_required",
    ):
        gateway.optimize_runtime_decision(
            issuer=IssueOnlyCore(),
            state={},
        )
