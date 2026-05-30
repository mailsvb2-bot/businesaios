from execution.governance_service import GovernanceService
from execution.headless_ledger import LedgerRecord


def test_governance_service_exposes_selection_and_promotion_decisions(tmp_path) -> None:
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

    service.ledger.write(LedgerRecord(run_id='run-1', trace_id='t1', business_id='biz', tenant_id='tenant', goal='grow', completed=True, stop_reason='goal_reached', steps_count=1, final_feedback={'goal_score': 0.91, 'goal_reached': True}, trace={'events': []}))
    service.ledger.write(LedgerRecord(run_id='run-2', trace_id='t2', business_id='biz', tenant_id='tenant', goal='grow', completed=False, stop_reason='execution_failed', steps_count=1, final_feedback={'goal_score': 0.10}, trace={'events': []}))

    selected = service.select_baseline(run_ids=['run-2', 'run-1'], baseline_name='baseline-1')
    assert selected is not None
    assert selected['run_id'] == 'run-1'
    assert selected['governance_decision']['decision_type'] == 'select_baseline'

    promoted = service.promote_baseline(baseline_name='baseline-1', run_id='run-1', label='manual')
    assert promoted['metadata']['governance_decision']['decision_type'] == 'promote_baseline'
    assert promoted['governance_decision']['selected_run_id'] == 'run-1'


def test_governance_service_exposes_rollback_decision(tmp_path) -> None:
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

    service.ledger.write(LedgerRecord(run_id='run-1', trace_id='t1', business_id='biz', tenant_id='tenant', goal='grow', completed=True, stop_reason='goal_reached', steps_count=1, final_feedback={'goal_score': 0.91, 'goal_reached': True}, trace={'events': []}))
    service.ledger.write(LedgerRecord(run_id='run-2', trace_id='t2', business_id='biz', tenant_id='tenant', goal='grow', completed=False, stop_reason='execution_failed', steps_count=1, final_feedback={'goal_score': 0.12, 'error': 'timeout'}, trace={'events': []}))
    service.promote_baseline(baseline_name='baseline-1', run_id='run-1', label='manual')

    recommendation = service.rollback_recommendation(baseline_name='baseline-1', candidate_run_id='run-2', fallback_run_ids=['run-1'])
    assert recommendation['governance_decision']['decision_type'] == 'rollback_recommendation'
    assert recommendation['governance_decision']['selected_run_id'] == 'run-1'
