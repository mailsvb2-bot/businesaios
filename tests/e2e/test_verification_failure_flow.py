from __future__ import annotations

import pytest

from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

def test_verification_failure_flow_keeps_execution_but_marks_unverified(tmp_path) -> None:
    harness = build_harness(tmp_path, scenario=[ScenarioStep(action_type="notify_owner", output={"verified": False, "goal_reached": False})])
    report = harness.run(make_request(goal="Publish listing with missing proof", max_steps=1))
    step = report.steps[0]
    assert step.attempted is True
    assert step.executed is True
    assert step.verified is False
    assert report.final_feedback["verification_failed"] is True
    assert report.final_feedback["goal_evaluation"]["achieved"] is False
