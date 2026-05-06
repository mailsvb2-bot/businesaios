from __future__ import annotations

from execution.governance_service import GovernanceService
from execution.headless_ledger import LedgerRecord


def test_governance_service_emits_canonical_governance_evidence(tmp_path) -> None:
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

    service.business_memory.remember_execution(
        tenant_id='tenant-1', business_id='biz-1', run_id='run-0', goal='grow', completed=False,
        stop_reason='execution_failed', final_feedback={'goal_score': 0.1, 'error': 'timeout'}, step_count=1,
        profile={}, constraints={}, signals=[], meta={}, channel='headless', region='eu', product_name='BusinesAIOS'
    )
    service.ledger.write(LedgerRecord(
        run_id='run-1', trace_id='trace-1', business_id='biz-1', tenant_id='tenant-1', goal='grow', completed=True,
        stop_reason='goal_reached', steps_count=1, final_feedback={'goal_score': 0.9, 'goal_reached': True}, trace={'events': []}
    ))
    baseline = service.promote_baseline(baseline_name='baseline-1', run_id='run-1', label='manual')
    metadata = dict(baseline.get('metadata') or {})
    assert metadata['governance_evidence']['baseline_name'] == 'baseline-1'
    assert metadata['governance_evidence']['candidate_run_id'] == 'run-1'

    drift = service.audit_drift(baseline_name='baseline-1', candidate_run_id='run-1')
    assert drift['governance_evidence']['drift']['severity'] in {'none', 'low', 'medium', 'high', ''}

    verify = service.verify_promotion_evidence(baseline_name='baseline-1')
    assert verify['ok'] is True
