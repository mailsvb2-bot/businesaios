from __future__ import annotations

from pathlib import Path

from execution.governance_service import GovernanceService
from execution.headless_ledger import LedgerRecord


def test_business_memory_governance_flow_end_to_end(tmp_path) -> None:
    import os
    cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        svc = GovernanceService.build_default()
        svc.business_memory.remember_execution(
            tenant_id="tenant-1", business_id="biz-1", run_id="run-1", goal="lead processing", completed=True,
            stop_reason="goal_reached", final_feedback={"goal_score": 0.85, "goal_reached": True}, step_count=1,
            profile={"segment": "services"}, constraints={}, signals=[], meta={"channel": "headless", "region": "eu"},
            channel="headless", region="eu", product_name="BusinesAIOS", recorded_at="2026-03-21T12:00:00Z"
        )
        svc.ledger.write(LedgerRecord(run_id="run-1", trace_id="trace-1", business_id="biz-1", tenant_id="tenant-1", goal="lead processing", completed=True, stop_reason="goal_reached", steps_count=1, final_feedback={"goal_score": 0.85, "goal_reached": True, "retry_classification": {"kind": "success"}}, trace={"events": []}))
        promoted = svc.promote_best_for_scenario(scenario="lead_processing", run_ids=["run-1"])
        assert promoted is not None
        drift = svc.audit_drift(baseline_name="scenario:lead_processing:golden", candidate_run_id="run-1")
        assert "business_memory_fit" in drift
    finally:
        os.chdir(cwd)
