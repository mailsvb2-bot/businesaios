from execution.governance_service import GovernanceService
from execution.headless_ledger import LedgerRecord


def test_governance_service_joined_history_returns_canonical_timeline(tmp_path) -> None:
    service = GovernanceService.build_default()
    service.ledger.root_dir = tmp_path / 'ledger'
    service.ledger.root_dir.mkdir(parents=True, exist_ok=True)
    service.baselines.root_dir = tmp_path / 'baselines'
    service.baselines.root_dir.mkdir(parents=True, exist_ok=True)
    service.history.root_dir = tmp_path / 'history'
    service.history.root_dir.mkdir(parents=True, exist_ok=True)
    service.rollback_manager.rollback_store.root_dir = tmp_path / 'rollbacks'
    service.rollback_manager.rollback_store.root_dir.mkdir(parents=True, exist_ok=True)
    service.business_memory.root_dir = tmp_path / 'memory'
    service.business_memory.root_dir.mkdir(parents=True, exist_ok=True)
    for rid, score, completed in [('run-1', 0.9, True), ('run-2', 0.2, False)]:
        service.ledger.write(LedgerRecord(run_id=rid, trace_id=rid, business_id='biz-1', tenant_id='tenant-1', goal='grow', completed=completed, stop_reason='goal_reached' if completed else 'execution_failed', steps_count=1, final_feedback={'goal_score': score, 'error': 'timeout' if not completed else ''}, trace={'run_id': rid}))
    service.promote_baseline(baseline_name='baseline-1', run_id='run-1', label='manual')
    service.rollback_baseline(baseline_name='baseline-1', fallback_run_id='run-1', reason='manual_guardrail')
    joined = service.joined_history(baseline_name='baseline-1', candidate_run_ids=['run-2'])
    assert joined['governance_timeline']['baseline_name'] == 'baseline-1'
    assert joined['baseline_snapshot']['governance_timeline']['current_source_run_id'] == 'run-1'
    assert joined['rollback_record']['governance_timeline']['rollback']['reason'] == 'manual_guardrail'
    assert joined['history_rows']
