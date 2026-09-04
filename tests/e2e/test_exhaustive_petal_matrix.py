from __future__ import annotations

import importlib
import itertools
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from application.capability.capability_matrix import CapabilityMatrix
from boot.factories.governance_chain_factory import build_governance_chain
from boot.registrations.simple_singletons import ActionBudget, KillSwitch, RewardGuard, RiskEngine, SimulationGate
from boot.runtime_service_specs import RUNTIME_SERVICE_SPECS
from core.actions.catalog import build_catalog
from core.autopilot.onboarding.schema import BudgetChoice, Diagnostics, HasClientsChoice
from core.autopilot.onboarding.state_machine import OnboardingSession, OnboardingStep, advance_with_callback, advance_with_text
from crm.onboarding.crm_connection_state_machine import CrmConnectionStateMachine, _ALLOWED
from execution.action_catalog import get_action_spec, known_action_types
from runtime.boot.actions_registry import BUILTIN_HANDLER_ACTIONS, INLINE_ALLOWLIST, SPECS
from runtime.boot.registration_manifest import registered_action_names
from runtime.bootstrap import bootstrap_runtime
from runtime.platform.support.import_doors import RUNTIME_PLATFORM_SUPPORT_IMPORT_DOORS
from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request


def _types(value: Any) -> tuple[type, ...]:
    return value if isinstance(value, tuple) else (value,)


def _sample(value: Any) -> Any:
    accepted = _types(value)
    selected = next((kind for kind in (str, int, float, bool, dict, list, tuple, set, object) if kind in accepted), accepted[0])
    return {str: "sample", int: 1, float: 1.25, bool: True, dict: {}, list: [], tuple: (), set: set(), object: "sample"}.get(selected, "sample")


def _wrong(value: Any) -> tuple[bool, Any]:
    accepted = _types(value)
    if object in accepted:
        return False, None
    for candidate in (None, "wrong", 7, 1.5, True, {}, [], ()):
        if not isinstance(candidate, accepted):
            return True, candidate
    return False, None


def test_every_declared_action_schema_accepts_only_its_contract() -> None:
    cases = 0
    for action_name, entry in sorted(build_catalog().items()):
        schema = entry.schema
        minimal = {name: _sample(schema.field_types.get(name, str)) for name in schema.required}
        full = {name: _sample(schema.field_types.get(name, str)) for name in schema.required | schema.optional}
        schema.validate(minimal)
        schema.validate(full)
        cases += 2
        for field in sorted(schema.required):
            payload = dict(minimal)
            payload.pop(field, None)
            with pytest.raises(ValueError, match="MISSING_REQUIRED_KEYS"):
                schema.validate(payload)
            cases += 1
        for field, field_type in sorted(schema.field_types.items()):
            available, value = _wrong(field_type)
            if not available:
                continue
            payload = dict(full)
            payload[field] = value
            with pytest.raises(ValueError, match="BAD_PAYLOAD_TYPE"):
                schema.validate(payload)
            cases += 1
        if not schema.allow_additional:
            with pytest.raises(ValueError, match="UNKNOWN_PAYLOAD_KEYS"):
                schema.validate({**minimal, "__unexpected_petal__": True})
            cases += 1
        for payload in (None, []):
            with pytest.raises(ValueError):
                schema.validate(payload)  # type: ignore[arg-type]
            cases += 1
    assert cases == 883


def test_every_runtime_handler_and_compatibility_import_door_resolves() -> None:
    registered = set(registered_action_names())
    for action_name, spec in sorted(SPECS.items()):
        if action_name in INLINE_ALLOWLIST or action_name in BUILTIN_HANDLER_ACTIONS:
            assert action_name in registered
            continue
        module_name, separator, attr = spec.handler_ref.partition(":")
        assert separator
        target: Any = importlib.import_module(module_name)
        for part in attr.split("."):
            target = getattr(target, part)
        assert callable(target), (action_name, spec.handler_ref)

    cases = 0
    for module_name, exports in sorted(RUNTIME_PLATFORM_SUPPORT_IMPORT_DOORS.items()):
        module = importlib.import_module(module_name)
        cases += 1
        for export_name in exports:
            assert hasattr(module, export_name), (module_name, export_name)
            cases += 1
    assert len(SPECS) == 59
    assert cases == 1016


def test_every_action_across_every_declared_capability_posture() -> None:
    matrix = CapabilityMatrix()
    states = {
        "healthy": {"enabled": True, "healthy": True, "health_score": 1.0, "observation_count": 1, "evidence_state": "sufficient"},
        "disabled": {"enabled": False, "healthy": False, "health_score": 1.0},
        "unhealthy": {"enabled": True, "healthy": False, "health_score": 0.0},
        "degraded": {"enabled": True, "healthy": False, "degraded": True, "health_score": 0.5},
        "stale": {"enabled": True, "healthy": False, "health_score": 0.7, "staleness_state": "stale"},
        "insufficient_evidence": {"enabled": True, "healthy": True, "health_score": 1.0, "observation_count": 0, "evidence_state": "insufficient"},
    }
    cases = 0
    for action_type in known_action_types():
        spec = get_action_spec(action_type)
        for state_name, state in states.items():
            record = matrix.record_for_action(action_type=action_type, runtime_capabilities={action_type: state})
            descriptor = record.descriptor
            assert descriptor.action_type == spec.action_type
            assert descriptor.capability_key == spec.action_class
            assert descriptor.executable == spec.executable
            assert descriptor.routable == spec.routable
            if state_name == "disabled":
                assert not record.runtime.enabled and record.runtime.routing_state == "disabled"
            if state_name == "healthy":
                assert record.runtime.healthy and record.runtime.routing_state == "enabled"
            if state_name == "degraded":
                assert record.runtime.degraded and record.runtime.routing_state == "fallback_preferred"
            if state_name == "stale":
                assert record.runtime.staleness_state == "stale"
            cases += 1
    assert cases == 270


def test_every_action_across_all_governance_gate_combinations() -> None:
    cases = 0
    for action_type in known_action_types():
        for kill_ok, reward_ok, simulation_ok, budget_ok, risk_ok in itertools.product((False, True), repeat=5):
            payload = {
                "action_type": action_type,
                "expected_reward": 0.0 if reward_ok else -1.0,
                "expected_margin": 0.0,
                "requires_simulation": True,
                "simulation_passed": simulation_ok,
                "planned_actions": 1 if budget_ok else 1001,
                "risk_score": 0.1 if risk_ok else 0.9,
                "max_allowed_risk_score": 0.8,
            }
            envelope = SimpleNamespace(decision=SimpleNamespace(action=action_type, payload=payload))
            chain = build_governance_chain(
                risk_engine=RiskEngine(), reward_guard=RewardGuard(), simulation_gate=SimulationGate(),
                kill_switch=KillSwitch(is_stopped=not kill_ok), action_budget=ActionBudget(max_actions=1000),
            )
            assert chain.evaluate(envelope) is (kill_ok and reward_ok and simulation_ok and budget_ok and risk_ok)
            cases += 1
    assert cases == 1440


def test_every_runtime_service_is_present_in_sovereign_boot(tmp_path: Path) -> None:
    runtime = bootstrap_runtime(project_root=str(tmp_path))
    actual = {str(item) for item in tuple(getattr(runtime, "services", ()) or ())}
    expected = {str(spec.service_name) for spec in RUNTIME_SERVICE_SPECS}
    assert expected <= actual
    assert bool(getattr(getattr(runtime, "state", None), "ready", False))
    assert len(expected) == 21


def test_every_action_through_headless_success_failure_and_capability_fallbacks(tmp_path: Path) -> None:
    variants = {
        "success": lambda action: ScenarioStep(action_type=action, output={"verified": True, "goal_reached": True, "terminal": True, "external_refs": [f"{action}:proof"]}),
        "unverified": lambda action: ScenarioStep(action_type=action, output={"verified": False, "goal_reached": False}),
        "executor_error": lambda action: ScenarioStep(action_type=action, ok=False, error="synthetic_executor_failure"),
    }
    cases = 0
    for index, action_type in enumerate(known_action_types()):
        spec = get_action_spec(action_type)
        healthy = {action_type: {"enabled": True, "healthy": True, "health_score": 1.0, "observation_count": 1, "evidence_state": "sufficient"}}
        for variant_name, factory in variants.items():
            harness = build_harness(tmp_path / f"{index}-{variant_name}", scenario=[factory(action_type)], runtime_capabilities=healthy)
            report = harness.run(make_request(goal=f"Exercise {action_type} {variant_name}", approval_policy={"allow_action_types": [action_type]}, meta={"runtime_capabilities": healthy}))
            assert report.steps
            if spec.routable and spec.executable:
                assert action_type in harness.executor.seen_actions
            if variant_name != "success":
                assert not report.verified
            cases += 1

        disabled = {action_type: {"enabled": False, "healthy": False, "health_score": 0.0}}
        harness = build_harness(tmp_path / f"{index}-disabled", scenario=[variants["success"](action_type)], runtime_capabilities=disabled)
        report = harness.run(make_request(goal=f"Exercise disabled {action_type}", approval_policy={"allow_action_types": [action_type]}, meta={"runtime_capabilities": disabled}))
        assert action_type not in harness.executor.seen_actions
        assert not (report.verified and report.steps and report.steps[0].action == action_type)
        cases += 1

        unhealthy = {action_type: {"enabled": True, "healthy": False, "health_score": 0.0, "evidence_state": "insufficient"}}
        harness = build_harness(tmp_path / f"{index}-unhealthy", scenario=[variants["success"](action_type)], runtime_capabilities=unhealthy)
        report = harness.run(make_request(goal=f"Exercise unhealthy {action_type}", approval_policy={"allow_action_types": [action_type]}, meta={"runtime_capabilities": unhealthy}))
        assert report.steps
        cases += 1
    assert cases == 225


def test_every_finite_user_flow_state_and_transition() -> None:
    crm = CrmConnectionStateMachine()
    states = tuple(_ALLOWED)
    crm_cases = 0
    for current, new in itertools.product(states, repeat=2):
        if new in _ALLOWED[current]:
            assert crm.transition(current, new) == new
        else:
            with pytest.raises(ValueError, match="Invalid CRM connection transition"):
                crm.transition(current, new)
        crm_cases += 1
    assert crm_cases == 36

    text_stages = {OnboardingStep.DIAG_WHAT, OnboardingStep.DIAG_AVG_CHECK, OnboardingStep.DIAG_MARGIN, OnboardingStep.DIAG_REGION}
    onboarding_cases = 0
    for stage in OnboardingStep:
        session = OnboardingSession(stage=stage, goal="profit_7d", diag=Diagnostics())
        assert advance_with_text(session, "") is None
        result = advance_with_text(session, "100")
        assert (result is not None) is (stage in text_stages)
        onboarding_cases += 2

    callback_sessions = OnboardingSession(stage=OnboardingStep.DIAG_HAS_CLIENTS, goal="profit_7d", diag=Diagnostics())
    callbacks = [
        *(f"autopilot:has_clients:{choice.value}" for choice in HasClientsChoice),
        *(f"autopilot:budget:{choice.value}" for choice in BudgetChoice),
        "autopilot:pick_channel:internal", "autopilot:pick_channel:external", "autopilot:pick_channel:unknown",
        "autopilot:ads_connect:vk", "autopilot:ads_connect:yandex", "autopilot:unknown:value",
    ]
    for callback in callbacks:
        result = advance_with_callback(callback_sessions, callback)
        assert (result is None) is callback.startswith("autopilot:unknown:")
        onboarding_cases += 1
    assert onboarding_cases == 37
