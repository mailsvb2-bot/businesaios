from __future__ import annotations
import pytest
from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

def test_restart_resume_flow_replays_from_ledger_record(tmp_path) -> None:
    first = build_harness(tmp_path / "first", scenario=[ScenarioStep(action_type="route_lead", output={"verified": True, "goal_reached": True, "terminal": True, "external_refs": ["crm:lead:replay"], "effector": {"verified": True, "external_ref": "crm:lead:replay"}})])
    original = first.run(make_request(goal="Resume a lead flow", max_steps=1))
    record = first.read_single_ledger_record()
    second = build_harness(tmp_path / "second", scenario=[ScenarioStep(action_type="route_lead", output={"verified": True, "goal_reached": True, "terminal": True, "external_refs": ["crm:lead:replay"], "effector": {"verified": True, "external_ref": "crm:lead:replay"}})], include_idempotency=False)
    replayed = second.replay.replay(record)
    assert replayed.goal == original.goal
    assert replayed.business_id == original.business_id
    assert replayed.completed is True
    assert replayed.steps[0].action == "route_lead"
    assert replayed.steps[0].verified is True
