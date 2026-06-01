from __future__ import annotations

import pytest

from tests.e2e._assertions import assert_feedback_contract_shape
from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

def test_hermetic_vs_live_effects_keep_same_feedback_contract_shape(tmp_path) -> None:
    hermetic = build_harness(tmp_path / "hermetic", scenario=[ScenarioStep(action_type="send_email", output={"verified": True, "external_refs": ["sandbox://mail/1"], "effector": {"verified": True, "external_ref": "sandbox://mail/1"}})])
    live = build_harness(tmp_path / "live", scenario=[ScenarioStep(action_type="send_email", output={"verified": True, "external_refs": ["smtp://mail/1"], "effector": {"verified": True, "external_ref": "smtp://mail/1"}})])
    hermetic_report = hermetic.run(make_request(goal="Hermetic email", max_steps=1, autonomy_tier="bounded_autonomy"))
    live_report = live.run(make_request(goal="Live email", max_steps=1, autonomy_tier="bounded_autonomy"))
    assert hermetic_report.steps[0].verified is True
    assert live_report.steps[0].verified is True
    assert "sandbox://mail/1" in hermetic_report.steps[0].execution_feedback.get("external_refs", [])
    assert "smtp://mail/1" in live_report.steps[0].execution_feedback.get("external_refs", [])
    assert_feedback_contract_shape(hermetic_report.final_feedback)
    assert_feedback_contract_shape(live_report.final_feedback)
    assert set(hermetic_report.final_feedback.keys()) == set(live_report.final_feedback.keys())
