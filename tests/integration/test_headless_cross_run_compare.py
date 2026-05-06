from __future__ import annotations

from execution.cross_run_comparator import CrossRunComparator
from execution.headless_ledger import FileHeadlessLedger, LedgerRecord
from execution.headless_trace import HeadlessTrace


def test_compare_two_persisted_runs(tmp_path) -> None:
    ledger = FileHeadlessLedger(root_dir=tmp_path / "ledger")

    trace_a = HeadlessTrace.start(goal="increase revenue", business_id="biz-1", tenant_id="tenant-1")
    trace_b = HeadlessTrace.start(goal="increase revenue", business_id="biz-1", tenant_id="tenant-1")

    ledger.write(
        LedgerRecord(
            run_id=trace_a.run_id,
            trace_id=trace_a.trace_id,
            business_id="biz-1",
            tenant_id="tenant-1",
            goal="increase revenue",
            completed=False,
            stop_reason="execution_failed",
            steps_count=1,
            final_feedback={"goal_score": 0.25},
            trace=trace_a.to_dict(),
        )
    )
    ledger.write(
        LedgerRecord(
            run_id=trace_b.run_id,
            trace_id=trace_b.trace_id,
            business_id="biz-1",
            tenant_id="tenant-1",
            goal="increase revenue",
            completed=True,
            stop_reason="goal_reached",
            steps_count=1,
            final_feedback={"goal_score": 0.85},
            trace=trace_b.to_dict(),
        )
    )

    comparator = CrossRunComparator()
    comparison = comparator.compare(
        baseline=ledger.read(trace_a.run_id),
        candidate=ledger.read(trace_b.run_id),
    )

    assert comparison.improved is True
    assert comparison.baseline_goal_score == 0.25
    assert comparison.candidate_goal_score == 0.85
