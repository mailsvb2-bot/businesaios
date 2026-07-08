from __future__ import annotations

import json
from pathlib import Path

from scripts.ci import step_user_scenario_gate


def test_user_scenario_gate_declares_rust_matrix_runner() -> None:
    assert callable(step_user_scenario_gate._run_rust_user_scenario_matrix)


def test_user_scenario_rust_matrix_fixture_is_declared() -> None:
    fixture = Path("safety_fixtures/businessaios_user_scenario_matrix_golden.json")
    payload = json.loads(fixture.read_text(encoding="utf-8"))

    assert payload["version"] == "businessaios_user_scenario_matrix.v1"
    assert len(payload["cases"]) >= 10
    scenarios = {case["scenario"] for case in payload["cases"]}
    assert {
        "capability_matrix",
        "connector_matrix",
        "cli_run",
        "cli_scenario",
        "sdk_execute",
    }.issubset(scenarios)
    assert any(case["expected"]["allowed"] is False for case in payload["cases"])
