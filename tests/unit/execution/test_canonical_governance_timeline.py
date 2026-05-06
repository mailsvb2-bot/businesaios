from execution.canonical_governance_timeline import (
    canonical_baseline_snapshot,
    canonical_governance_history_row,
    canonical_governance_timeline,
    canonical_rollback_record,
)


def test_canonical_governance_timeline_contract_builds_shared_shape() -> None:
    baseline = canonical_baseline_snapshot(
        baseline_name='b1',
        source_run_id='run-1',
        promoted_at_label='manual',
        record={'run_id': 'run-1', 'goal': 'grow', 'tenant_id': 't1', 'business_id': 'biz1'},
        metadata={'governance_evidence': {'governance_action': 'promote_baseline', 'business_memory_summary': {'tenant_id': 't1', 'business_id': 'biz1', 'total_runs': 1}}},
    )
    row = canonical_governance_history_row(baseline_name='b1', event_type='promoted', source_run_id='run-1', payload={'promoted_at_label': 'manual'})
    rollback = canonical_rollback_record(baseline_name='b1', previous_source_run_id='run-1', new_source_run_id='run-0', reason='high_drift')
    timeline = canonical_governance_timeline(
        baseline_name='b1',
        baseline_snapshot=baseline,
        history_rows=[row],
        rollback_record=rollback,
        drift_reports=[{'candidate_run_id': 'run-2', 'severity': 'high'}],
    )
    assert timeline['baseline_snapshot']['governance_timeline']['baseline_name'] == 'b1'
    assert timeline['rollback_record']['governance_timeline']['rollback']['reason'] == 'high_drift'
    assert timeline['history_rows'][0]['governance_timeline_row']['event_type'] == 'promoted'
    assert timeline['drift_summary']['high_count'] == 1
