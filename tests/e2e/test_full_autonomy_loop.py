from __future__ import annotations
import pytest
from tests.e2e._assertions import assert_feedback_contract_shape, assert_report_ledger_snapshot_consistency, assert_step_report_consistency
from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

def test_full_autonomy_loop(tmp_path) -> None:
    harness = build_harness(tmp_path, scenario=[
        ScenarioStep(action_type="create_experiment", output={"verified": True, "goal_reached": False, "external_refs": ["internal:1"]}),
        ScenarioStep(action_type="notify_owner", output={"verified": True, "goal_reached": True, "terminal": True, "external_refs": ["internal:2"]}),
    ])
    report = harness.run(make_request(goal="Acquire and verify a lead", max_steps=2))
    assert report.completed is True
    assert report.stop_reason == "goal_achieved"
    assert len(report.steps) == 2
    for step in report.steps:
        assert_step_report_consistency(step)
    assert report.steps[-1].verified is True
    assert report.final_feedback["goal_evaluation"]["achieved"] is True
    assert_feedback_contract_shape(report.final_feedback)
    ledger = harness.read_single_ledger_record()
    snapshot = harness.read_latest_state_snapshot(ledger["run_id"])
    assert_report_ledger_snapshot_consistency(report=report, ledger=ledger, snapshot=snapshot)
    effect_rows = harness.read_effect_rows(ledger["run_id"])
    assert len(effect_rows) == 2
