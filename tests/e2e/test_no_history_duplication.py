from __future__ import annotations
import pytest
from tests.e2e._assertions import assert_recent_actions_deduped
from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

def test_no_history_duplication_when_same_action_reappears(tmp_path) -> None:
    harness = build_harness(tmp_path, scenario=[
        ScenarioStep(action_type="create_listing", decision_id="dec-stable", output={"verified": True, "external_refs": ["listing:1"], "effector": {"verified": True, "external_ref": "listing:1"}}),
        ScenarioStep(action_type="create_listing", decision_id="dec-stable", output={"verified": True, "external_refs": ["listing:1"], "effector": {"verified": True, "external_ref": "listing:1"}}),
    ])
    report = harness.run(make_request(goal="Exercise recent action dedupe", max_steps=2))
    recent_actions = report.final_feedback["recent_actions"]
    assert_recent_actions_deduped(report.final_feedback)
    assert len(recent_actions) == 1
    assert recent_actions[0]["action_id"] == "action:dec-stable"
