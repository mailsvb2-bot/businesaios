from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import application.headless.contract as headless_contract
import bootstrap.decision_core_contract as canonical_contract
import core.ai as core_ai
from application.capability.capability_aware_planning import CapabilityAwarePlanner
from application.capability.capability_health_registry import CapabilityHealthRegistry
from application.capability.capability_matrix import CapabilityMatrix
from application.capability.capability_router import ExecutionCapabilityRouter


class OptimizeCore:
    def optimize(self, state):
        return SimpleNamespace(
            decision=SimpleNamespace(
                decision_id="decision",
                correlation_id="correlation",
                action="noop",
                payload={},
            ),
            state=state,
        )


class Executor:
    def execute(self, envelope):
        return envelope


class Mapper:
    def to_world_state(self, request):
        return request


@pytest.fixture(autouse=True)
def reset_singleton():
    core_ai._reset_decision_core_singleton_for_tests()
    yield
    core_ai._reset_decision_core_singleton_for_tests()


def build_contract(**kwargs):
    return headless_contract.HeadlessExecutionContract(
        decision_core=OptimizeCore(),
        executor=Executor(),
        state_mapper=Mapper(),
        **kwargs,
    )


def test_core_ai_lazy_alias_and_boot_identity_guard(monkeypatch):
    sentinel = object()
    importer = Mock(return_value=sentinel)
    monkeypatch.setattr(core_ai.importlib, "import_module", importer)
    core_ai.__dict__.pop("decision_trace", None)

    assert core_ai.__getattr__("decision_trace") is sentinel
    assert core_ai.__dict__["decision_trace"] is sentinel
    importer.assert_called_once_with("core.decision.ai_decision_trace")
    with pytest.raises(AttributeError, match="no attribute 'missing_alias'"):
        core_ai.__getattr__("missing_alias")

    with pytest.raises(RuntimeError, match="DECISIONCORE_NOT_INITIALIZED"):
        core_ai.get_decision_core_singleton()
    with pytest.raises(TypeError, match="DECISIONCORE_MISSING"):
        core_ai.set_decision_core_singleton(None)

    registered = object()
    core_ai.set_decision_core_singleton(registered)
    core_ai.set_decision_core_singleton(registered)
    assert core_ai.get_decision_core_singleton() is registered
    assert core_ai.require_decision_core_singleton() is registered
    assert core_ai.require_decision_core_singleton(registered) is registered
    with pytest.raises(RuntimeError, match="NONCANONICAL_DECISIONCORE"):
        core_ai.require_decision_core_singleton(object())

    import core.observability.arch_violation as arch_violation
    import core.runtime.safe_mode as safe_mode

    log_violation = Mock()
    enter_safe_mode = Mock()
    monkeypatch.setattr(arch_violation, "log_arch_violation", log_violation)
    monkeypatch.setattr(safe_mode, "enter_safe_mode", enter_safe_mode)
    with pytest.raises(SystemExit, match="ARCH_VIOLATION: MULTI_DECISIONCORE"):
        core_ai.set_decision_core_singleton(object())
    log_violation.assert_called_once_with("MULTI_DECISIONCORE")
    enter_safe_mode.assert_called_once_with("MULTI_DECISIONCORE")
    assert core_ai.get_decision_core_singleton() is registered


def test_decision_contract_is_data_only_and_compat_module_reexports_it():
    class IssueOnly:
        def issue(self, state):
            return state

    class OptimizeOnly:
        def optimize(self, state):
            return state

    assert isinstance(IssueOnly(), canonical_contract.RuntimeDecisionIssuePort)
    assert isinstance(
        OptimizeOnly(),
        canonical_contract.RuntimeDecisionOptimizePort,
    )
    compat = importlib.reload(
        importlib.import_module("runtime.boot.decision_core_contract")
    )
    assert compat.RuntimeDecisionCorePort is canonical_contract.RuntimeDecisionCorePort
    assert compat.RuntimeDecisionIssuePort is canonical_contract.RuntimeDecisionIssuePort
    assert (
        compat.RuntimeDecisionOptimizePort
        is canonical_contract.RuntimeDecisionOptimizePort
    )


def test_headless_contract_rejects_only_real_surface_defects(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(
        ValueError,
        match=r"decision_core must provide callable issue\(\) or optimize\(\)",
    ):
        headless_contract.HeadlessExecutionContract(
            decision_core=object(),
            executor=Executor(),
            state_mapper=Mapper(),
        )

    with pytest.raises(
        ValueError,
        match=r"state_mapper must provide callable to_world_state\(\)",
    ):
        headless_contract.HeadlessExecutionContract(
            decision_core=OptimizeCore(),
            executor=Executor(),
            state_mapper=object(),
        )


def test_headless_contract_normalizes_registry_and_preserves_shared_planner(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    matrix = CapabilityMatrix()
    foreign_registry = CapabilityHealthRegistry(
        root_dir=tmp_path / "foreign-health",
        matrix=CapabilityMatrix(),
    )
    normalized = build_contract(
        capability_matrix=matrix,
        capability_health_registry=foreign_registry,
    )
    assert normalized._capability_health_registry._matrix is matrix
    assert normalized._capability_health_registry is not foreign_registry

    registry = CapabilityHealthRegistry(
        root_dir=tmp_path / "shared-health",
        matrix=matrix,
    )
    router = ExecutionCapabilityRouter(
        matrix=matrix,
        health_registry=registry,
    )
    planner = CapabilityAwarePlanner(router=router)
    shared = build_contract(
        capability_matrix=matrix,
        capability_health_registry=registry,
        capability_aware_planner=planner,
    )
    assert shared._execution_capability_router is router
    assert shared._capability_aware_planner is planner


def _execution_request():
    return SimpleNamespace(
        goal="grow",
        business_id="business",
        tenant_id="tenant",
        user_id="user",
        product_name="product",
        region="ru",
        channel="headless",
        profile={"p": 1},
        signals=[{"s": 1}],
        constraints={"max_spend_rub": 1000},
        economy={"currency": "RUB"},
        meta={"m": 1},
        ceo=SimpleNamespace(),
        autonomy_tier="supervised",
        approval_policy={"required": True},
    )


def test_execute_once_preserves_every_request_field_and_bounds_steps():
    contract = object.__new__(headless_contract.HeadlessExecutionContract)
    contract.execute_autopilot = Mock(return_value="report")
    request = _execution_request()

    assert contract.execute_once(request) == "report"
    bounded = contract.execute_autopilot.call_args.args[0]
    assert bounded.goal == request.goal
    assert bounded.profile == request.profile
    assert bounded.signals == request.signals
    assert bounded.constraints == request.constraints
    assert bounded.economy == request.economy
    assert bounded.meta == request.meta
    assert bounded.max_steps == 1


def test_execute_autopilot_always_persists_evidence_and_optionally_ledger():
    step = SimpleNamespace(
        step_index=2,
        action="notify_owner",
        action_id="action-1",
        decision_id="decision-1",
        correlation_id="correlation-1",
        attempted=True,
        executed=True,
        verified=True,
        operator_required=False,
        verification_status="verified",
        status="completed",
        reason="done",
        payload={},
        evidence={},
        feedback={},
        execution_feedback={
            "attempted": True,
            "executed": True,
            "verified": True,
            "verification_status": "verified",
        },
    )
    trace = SimpleNamespace(
        run_id="run-1",
        trace_id="trace-1",
        to_dict=lambda: {"trace_id": "trace-1"},
    )
    evidence = Mock()
    ledger = Mock()
    contract = object.__new__(headless_contract.HeadlessExecutionContract)
    contract._loop = SimpleNamespace(
        run=Mock(
            return_value=SimpleNamespace(
                completed=True,
                stop_reason="completed",
                steps=[step],
                final_feedback={
                    "execution_feedback": dict(step.execution_feedback)
                },
                trace=trace,
            )
        )
    )
    contract._evidence_persistence_service = evidence
    contract._ledger = ledger

    report = contract.execute_autopilot(_execution_request())

    assert report.completed is True
    assert report.canonical_run_artifact["steps_count"] == 1
    assert evidence.persist.call_args.kwargs["step_index"] == 2
    assert evidence.persist.call_args.kwargs["action"] == {
        "action_type": "notify_owner",
        "action_id": "action-1",
    }
    ledger.write.assert_called_once()

    contract._loop.run.return_value = SimpleNamespace(
        completed=False,
        stop_reason="no_action",
        steps=[],
        final_feedback={},
        trace=trace,
    )
    contract._ledger = None
    second = contract.execute_autopilot(_execution_request())
    assert second.completed is False
    assert evidence.persist.call_args.kwargs["step_index"] == 0
    assert evidence.persist.call_args.kwargs["action"] == {
        "action_type": "",
        "action_id": "",
    }
