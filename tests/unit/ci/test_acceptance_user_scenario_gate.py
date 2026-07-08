from __future__ import annotations

from pathlib import Path

from scripts.ci.plan_registry import allowed_gates, plan_for_gate
from scripts.ci.step_registry import handler_for_step
from scripts.ci.user_scenario_targets import USER_SCENARIO_MARK_EXPRESSION, USER_SCENARIO_TARGETS


def test_acceptance_gate_is_registered_as_user_scenario_gate() -> None:
    assert "acceptance" in allowed_gates()
    assert tuple(step.name for step in plan_for_gate("acceptance").steps) == (
        "assert-project-shape",
        "dependency-lock",
        "doctor-check",
        "user-scenario-gate",
    )
    assert callable(handler_for_step("user-scenario-gate"))


def test_user_scenario_gate_targets_existing_user_surfaces() -> None:
    assert USER_SCENARIO_MARK_EXPRESSION == "not slow and not gate"
    assert USER_SCENARIO_TARGETS == (
        "tests/integration/headless/test_cli_capability_matrix.py",
        "tests/integration/headless/test_cli_connector_matrix.py",
        "tests/integration/headless/test_cli_run_smoke.py",
        "tests/integration/headless/test_cli_scenario_smoke.py",
        "tests/integration/headless/test_sdk_execute_smoke.py",
    )
    for target in USER_SCENARIO_TARGETS:
        assert Path(target).exists(), target
