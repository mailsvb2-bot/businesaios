from execution.governance_service import GovernanceService
from execution.headless_ledger import LedgerRecord


def test_governance_advanced_roundtrip(tmp_path, monkeypatch) -> None:
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
    service.scenario_catalog.root_dir = tmp_path / 'catalog'
    service.scenario_catalog.root_dir.mkdir(parents=True, exist_ok=True)

    for rid, score, completed in [('run-1', 0.9, True), ('run-2', 0.2, False)]:
        service.ledger.write(LedgerRecord(run_id=rid, trace_id=rid, business_id='biz-1', tenant_id='tenant-1', goal='grow', completed=completed, stop_reason='goal_reached' if completed else 'execution_failed', steps_count=1, final_feedback={'goal_score': score, 'error': 'timeout' if not completed else ''}, trace={'run_id': rid}))
    service.business_memory.remember_execution(tenant_id='tenant-1', business_id='biz-1', run_id='run-0', goal='grow', completed=False, stop_reason='execution_failed', final_feedback={'goal_score': 0.1, 'error': 'timeout'}, step_count=1, profile={}, constraints={}, signals=[], meta={}, channel='headless', region='eu', product_name='BusinesAIOS')
    service.promote_baseline(baseline_name='baseline-1', run_id='run-1', label='manual')
    rr = service.rollback_recommendation(baseline_name='baseline-1', candidate_run_id='run-2', fallback_run_ids=['run-1'])
    assert rr['recommended_run_id'] == 'run-1'
    joined = service.joined_history(baseline_name='baseline-1', candidate_run_ids=['run-2'])
    assert joined['drift_summary']['samples'] == 1
    verify = service.verify_promotion_evidence(baseline_name='baseline-1')
    assert 'ok' in verify
