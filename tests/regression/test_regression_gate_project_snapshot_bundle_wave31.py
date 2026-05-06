from __future__ import annotations

from formal.regression_gate.project_snapshot_bundle import (
    load_project_snapshot_bundle,
    run_project_snapshot_bundle,
    summarize_project_snapshot_bundle,
)


def test_project_snapshot_bundle_is_present_and_mixed_wave31() -> None:
    summary = summarize_project_snapshot_bundle()
    assert summary["ok"]
    assert summary["count"] >= 5
    assert set(summary["scenario_types"]) == {"demand_bridge", "runtime"}


def test_project_snapshot_bundle_replays_current_project_contracts_wave31() -> None:
    report = run_project_snapshot_bundle()
    assert report["checked_cases"] >= 5
    assert report["ok"], report["failing_cases"]


def test_project_snapshot_cases_are_trace_complete_wave31() -> None:
    cases = load_project_snapshot_bundle()
    names = {case.name for case in cases}
    assert "demand_bridge_snapshot_selected_business" in names
    for case in cases:
        assert "trace" in case.expected_contract
        assert "decision_path" in case.expected_trace or case.scenario_type == "runtime"
