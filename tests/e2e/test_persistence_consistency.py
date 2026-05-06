from __future__ import annotations
import pytest
from tests.e2e._assertions import assert_report_ledger_snapshot_consistency
from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

def test_persistence_consistency_between_report_ledger_and_state(tmp_path) -> None:
    harness = build_harness(tmp_path, scenario=[ScenarioStep(action_type="route_lead", output={"verified": True, "goal_reached": True, "terminal": True, "external_refs": ["crm:lead:42"], "effector": {"verified": True, "external_ref": "crm:lead:42"}})])
    report = harness.run(make_request(goal="Persist a verified lead", max_steps=1))
    ledger = harness.read_single_ledger_record()
    snapshot = harness.read_latest_state_snapshot(ledger["run_id"])
    memory = harness.business_memory_store.load(tenant_id="tenant-1", business_id="biz-1")
    assert_report_ledger_snapshot_consistency(report=report, ledger=ledger, snapshot=snapshot)
    assert ledger["final_feedback"]["verification_status"] == report.final_feedback["verification_status"]
    assert memory.last_run is not None
    assert memory.last_run.run_id == ledger["run_id"]
