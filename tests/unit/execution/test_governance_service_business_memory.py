from __future__ import annotations

from pathlib import Path

from execution.governance_service import GovernanceService
from execution.headless_ledger import FileHeadlessLedger, LedgerRecord


def test_governance_service_includes_business_memory_evidence_in_promotion(tmp_path) -> None:
    cwd = Path.cwd()
    try:
        import os
        os.chdir(tmp_path)
        svc = GovernanceService.build_default()
        svc.business_memory.remember_execution(
            tenant_id="tenant-1", business_id="biz-1", run_id="run-1", goal="increase revenue", completed=True,
            stop_reason="goal_reached", final_feedback={"goal_score": 0.9, "goal_reached": True}, step_count=1,
            profile={"segment": "services"}, constraints={}, signals=[], meta={"channel": "headless", "region": "eu"},
            channel="headless", region="eu", product_name="BusinesAIOS", recorded_at="2026-03-21T12:00:00Z"
        )
        svc.ledger.write(LedgerRecord(run_id="run-1", trace_id="t1", business_id="biz-1", tenant_id="tenant-1", goal="increase revenue", completed=True, stop_reason="goal_reached", steps_count=1, final_feedback={"goal_score": 0.9, "goal_reached": True}, trace={"events": []}))
        baseline = svc.promote_baseline(baseline_name="golden", run_id="run-1", label="manual")
        metadata = dict(baseline.get("metadata") or {})
        assert "business_memory_summary" in metadata
        assert "business_memory_fit" in metadata
    finally:
        os.chdir(cwd)
