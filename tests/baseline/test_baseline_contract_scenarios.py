from __future__ import annotations

from pathlib import Path

from scripts.ci.baseline_contract import BASELINE_REQUIREMENTS
from scripts.ci.plan_registry import plan_for_gate
from scripts.ci.regression_impact_dotfix import blocked_artifact_paths, required_fast_steps_for_paths
from scripts.ci import step_doctor, step_registry
from tests.arch.test_agi_no_second_brain_surfaces import FORBIDDEN_SURFACES


def _requirement(requirement_id: str):
    for requirement in BASELINE_REQUIREMENTS:
        if requirement.requirement_id == requirement_id:
            return requirement
    raise AssertionError(f"missing baseline requirement: {requirement_id}")


def _gate_steps(gate: str) -> tuple[str, ...]:
    return tuple(step.name for step in plan_for_gate(gate).steps)


def _assert_scenario_self_reference(requirement_id: str, test_name: str) -> None:
    requirement = _requirement(requirement_id)
    assert requirement.scenario_ref.endswith(f"::{test_name}")


def test_baseline_single_decision_flow_contract_is_declared() -> None:
    _assert_scenario_self_reference("BAIOS-BASE-001", "test_baseline_single_decision_flow_contract_is_declared")
    requirement = _requirement("BAIOS-BASE-001")
    assert requirement.domain == "decision-core"
    assert "DecisionCore" in requirement.title


def test_baseline_no_second_brain_contract_reuses_arch_lock() -> None:
    _assert_scenario_self_reference("BAIOS-BASE-002", "test_baseline_no_second_brain_contract_reuses_arch_lock")
    assert FORBIDDEN_SURFACES
    for rel in FORBIDDEN_SURFACES:
        assert not Path(rel).exists(), f"forbidden second-brain surface exists: {rel}"


def test_baseline_runtime_execution_contract_has_registry_lock() -> None:
    _assert_scenario_self_reference("BAIOS-BASE-003", "test_baseline_runtime_execution_contract_has_registry_lock")
    fast_steps = _gate_steps("fast")
    assert "architecture-bypass-scan" in fast_steps
    assert "lock-tests" in fast_steps
    assert {"boot-smoke", "architecture-bypass-scan", "lock-tests"}.issubset(
        required_fast_steps_for_paths(("runtime/boot/actions_registry.py",))
    )


def test_baseline_ci_build_release_gate_sees_matrix() -> None:
    _assert_scenario_self_reference("BAIOS-BASE-004", "test_baseline_ci_build_release_gate_sees_matrix")
    for gate in ("fast", "full", "release", "pre-release"):
        assert "regression-impact" in _gate_steps(gate)
    release_steps = _gate_steps("release")
    assert release_steps.index("regression-impact") < release_steps.index("build-artifact")


def test_baseline_public_surface_contract_has_import_scenario() -> None:
    _assert_scenario_self_reference("BAIOS-BASE-005", "test_baseline_public_surface_contract_has_import_scenario")
    assert step_doctor.run is step_registry.run_doctor


def test_baseline_generated_artifact_contract_is_blocked() -> None:
    _assert_scenario_self_reference("BAIOS-BASE-006", "test_baseline_generated_artifact_contract_is_blocked")
    assert blocked_artifact_paths(("runtime/data/security/events.jsonl",)) == ("runtime/data/security/events.jsonl",)
    assert blocked_artifact_paths(("core/decision/runtime.py",)) == ()


def test_baseline_storage_compatibility_contract_is_mapped() -> None:
    _assert_scenario_self_reference("BAIOS-BASE-007", "test_baseline_storage_compatibility_contract_is_mapped")
    required = required_fast_steps_for_paths(("storage/evidence_store.py",))
    assert "import-smoke" in required
    assert "lock-tests" in required


def test_baseline_billing_recovery_contract_is_mapped() -> None:
    _assert_scenario_self_reference("BAIOS-BASE-008", "test_baseline_billing_recovery_contract_is_mapped")
    required = required_fast_steps_for_paths(("billing/recovery_store.py",))
    assert "import-smoke" in required
    assert "lock-tests" in required
