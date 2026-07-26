from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import runtime.decision_gateway as gateway
import runtime.decision_path_lock as path_lock
from core.ai import _reset_decision_core_singleton_for_tests


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


def test_path_lock_rejects_invalid_transitions_states_and_envelopes():
    spec = path_lock.DecisionPathLockSpec()
    assert spec.index_of("world_state") == 0
    with pytest.raises(path_lock.DecisionPathLockError, match="unknown_decision_stage"):
        spec.index_of("missing")
    with pytest.raises(path_lock.DecisionPathLockError, match="invalid_decision_transition"):
        spec.require_transition(current_stage="world_state", next_stage="executor")

    with pytest.raises(path_lock.DecisionPathLockError, match="decision_world_state_missing"):
        path_lock.lock_world_state(state=None)
    with pytest.raises(path_lock.DecisionPathLockError, match="must_not_be_envelope"):
        path_lock.lock_world_state(state=SimpleNamespace(decision=object()))
    with pytest.raises(path_lock.DecisionPathLockError, match="must_not_be_action_like"):
        path_lock.lock_world_state(state=SimpleNamespace(action="x", payload={}))

    with pytest.raises(path_lock.DecisionPathLockError, match="missing_decision"):
        path_lock.lock_decision_for_executor(envelope=object())
    with pytest.raises(path_lock.DecisionPathLockError, match="missing_decision_id"):
        path_lock.lock_decision_for_executor(
            envelope=SimpleNamespace(
                decision=SimpleNamespace(decision_id="", correlation_id="c")
            )
        )
    with pytest.raises(path_lock.DecisionPathLockError, match="missing_correlation_id"):
        path_lock.lock_decision_for_executor(
            envelope=SimpleNamespace(
                decision=SimpleNamespace(decision_id="d", correlation_id="")
            )
        )


def test_issue_locked_decision_validates_result_and_locks_executor_stage():
    core = OptimizeOnlyCore()
    locked = path_lock.issue_locked_decision(
        decision_core=core,
        state={"ok": True},
    )
    assert locked.stage == "decision_core"
    assert locked.envelope is core.result
    executor_locked = path_lock.lock_decision_for_executor(envelope=locked.envelope)
    assert executor_locked.stage == "executor"

    broken = OptimizeOnlyCore(result=object())
    with pytest.raises(path_lock.DecisionPathLockError, match="missing_decision"):
        path_lock.issue_locked_decision(
            decision_core=broken,
            state={},
        )


def test_runtime_route_gateway_success_and_fail_closed_branches(monkeypatch):
    core = OptimizeOnlyCore()
    service = SimpleNamespace(read_packet=Mock(return_value={"contract": True}))
    enrichment = SimpleNamespace(build=Mock(return_value={"signal": 7}))
    observability = SimpleNamespace(
        record_model_snapshot=Mock(),
        record_decision_trace=Mock(),
    )
    route = gateway.build_runtime_decision_gateway(
        decision_input_service=service,
        enrichment_service=enrichment,
        observability=observability,
    )
    packet = SimpleNamespace(
        packet_id="packet-1",
        recommendation_packet=SimpleNamespace(
            world_state=SimpleNamespace(generated_at_ms=123)
        ),
    )
    bound = gateway.build_runtime_decision_callable(issuer=core)

    observed = route.route(
        packet=packet,
        canonical_context={"tenant": "t"},
        decision_core_callable=bound,
    )
    assert observed is core.result
    assert core.calls == [{"tenant": "t", "signal": 7}]
    observability.record_model_snapshot.assert_called_once()
    trace = observability.record_decision_trace.call_args.kwargs
    assert trace["packet_id"] == "packet-1"
    assert trace["generated_at_ms"] == 123

    with pytest.raises(gateway.DecisionGatewayContractError, match="noncanonical_decision_callable"):
        route.route(
            packet=packet,
            canonical_context={},
            decision_core_callable=lambda state: state,
        )

    enrichment.build.return_value = []
    with pytest.raises(gateway.DecisionGatewayContractError, match="enrichment_must_be_mapping"):
        route.route(
            packet=packet,
            canonical_context={},
            decision_core_callable=bound,
        )

    enrichment.build.return_value = {}
    fallback_packet = SimpleNamespace(
        packet_id="",
        recommendation_packet=SimpleNamespace(
            world_state=SimpleNamespace(generated_at_ms=None)
        ),
    )
    route.route(
        packet=fallback_packet,
        canonical_context={},
        decision_core_callable=bound,
    )
    fallback_trace = observability.record_decision_trace.call_args.kwargs
    assert fallback_trace["packet_id"] == "decision_packet"
    assert fallback_trace["generated_at_ms"] == 0


def test_runtime_gateway_wraps_path_and_execution_errors(monkeypatch):
    core = OptimizeOnlyCore()

    monkeypatch.setattr(
        path_lock,
        "issue_locked_decision",
        Mock(side_effect=path_lock.DecisionPathLockError("path_failed")),
    )
    with pytest.raises(gateway.DecisionGatewayContractError, match="path_failed"):
        gateway.issue_runtime_decision(issuer=core, state={})

    direct = gateway.DecisionGatewayContractError("already_gateway")
    monkeypatch.setattr(
        path_lock,
        "issue_locked_decision",
        Mock(side_effect=direct),
    )
    with pytest.raises(gateway.DecisionGatewayContractError, match="already_gateway"):
        gateway.issue_runtime_decision(issuer=core, state={})

    monkeypatch.setattr(path_lock, "issue_locked_decision", lambda **kwargs: SimpleNamespace(envelope=core.result))
    import runtime.execution.execution_path_lock as execution_lock

    monkeypatch.setattr(
        execution_lock,
        "lock_execution_envelope",
        Mock(side_effect=RuntimeError("execution_lock_failed")),
    )
    with pytest.raises(gateway.DecisionGatewayContractError, match="execution_lock_failed"):
        gateway.execute_runtime_decision(
            issuer=core,
            executor=SimpleNamespace(execute=lambda value: value),
            state={},
        )

    monkeypatch.setattr(
        execution_lock,
        "lock_execution_envelope",
        Mock(side_effect=direct),
    )
    with pytest.raises(gateway.DecisionGatewayContractError, match="already_gateway"):
        gateway.execute_runtime_decision(
            issuer=core,
            executor=SimpleNamespace(execute=lambda value: value),
            state={},
        )


def test_route_and_issue_uses_only_canonical_callable():
    core = OptimizeOnlyCore()
    route = Mock()
    route.route.return_value = "routed"
    packet = SimpleNamespace()

    observed = gateway.route_and_issue_runtime_decision(
        route_gateway=route,
        issuer=core,
        packet=packet,
        canonical_context={"a": 1},
    )

    assert observed == "routed"
    kwargs = route.route.call_args.kwargs
    assert kwargs["packet"] is packet
    assert kwargs["canonical_context"] == {"a": 1}
    assert type(kwargs["decision_core_callable"]).__name__ == "_CanonicalDecisionCallable"


def test_contract_types_are_single_source_and_accept_either_alias():
    from bootstrap import decision_core_contract as canonical_contract
    from runtime.boot import decision_core_contract as compat_contract

    assert compat_contract.RuntimeDecisionCorePort is canonical_contract.RuntimeDecisionCorePort
    assert canonical_contract.RUNTIME_DECISION_CORE_COMPAT_METHODS == (
        "issue",
        "optimize",
    )
    assert isinstance(IssueOnlyCore(), canonical_contract.RuntimeDecisionIssuePort)
    assert isinstance(
        OptimizeOnlyCore(),
        canonical_contract.RuntimeDecisionOptimizePort,
    )
