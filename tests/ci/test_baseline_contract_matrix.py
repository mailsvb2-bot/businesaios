from __future__ import annotations

from pathlib import Path

from scripts.ci.baseline_contract import (
    BASELINE_REQUIREMENTS,
    baseline_requirement_ids,
    missing_scenario_paths,
    required_gates,
)
from scripts.ci.plan_registry import plan_for_gate
from scripts.ci.step_baseline_contract import run as run_baseline_contract


def _gate_steps(gate: str) -> tuple[str, ...]:
    return tuple(step.name for step in plan_for_gate(gate).steps)


def test_baseline_requirement_ids_are_unique_and_stable() -> None:
    ids = baseline_requirement_ids()
    assert ids == tuple(sorted(ids))
    assert len(ids) == len(set(ids))
    assert ids == tuple(f"BAIOS-BASE-{index:03d}" for index in range(1, len(ids) + 1))


def test_every_baseline_requirement_has_a_real_scenario() -> None:
    assert BASELINE_REQUIREMENTS
    assert missing_scenario_paths() == ()
    for requirement in BASELINE_REQUIREMENTS:
        assert "::test_" in requirement.scenario_ref
        path, test_name = requirement.scenario_ref.split("::", 1)
        text = Path(path).read_text(encoding="utf-8")
        assert f"def {test_name}" in text


def test_required_ci_build_release_gates_see_regression_impact_enforcement() -> None:
    assert required_gates() == ("fast", "full", "pre-release", "release")
    for gate in required_gates():
        steps = _gate_steps(gate)
        assert "regression-impact" in steps
        assert steps.index("regression-impact") < steps.index("import-smoke")
    release_steps = _gate_steps("release")
    assert release_steps.index("regression-impact") < release_steps.index("verify-release")
    assert release_steps.index("regression-impact") < release_steps.index("build-artifact")


def test_baseline_contract_step_runs_referenced_scenarios() -> None:
    ok, message = run_baseline_contract()
    assert ok, message
    assert "baseline contract matrix passed" in message
