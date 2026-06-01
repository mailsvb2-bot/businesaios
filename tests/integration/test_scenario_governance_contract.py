from execution.governance_service import GovernanceService
from execution.headless_ledger import LedgerRecord


def test_promote_best_for_scenario_exposes_canonical_scenario_governance(tmp_path) -> None:
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
    service.scenario_catalog.root_dir = tmp_path / 'scenario_catalog'
    service.scenario_catalog.root_dir.mkdir(parents=True, exist_ok=True)

    service.ledger.write(LedgerRecord(run_id='run-1', trace_id='t1', business_id='biz', tenant_id='tenant', goal='grow', completed=True, stop_reason='goal_reached', steps_count=1, final_feedback={'goal_score': 0.93, 'goal_reached': True}, trace={'events': []}))
    service.ledger.write(LedgerRecord(run_id='run-2', trace_id='t2', business_id='biz', tenant_id='tenant', goal='grow', completed=False, stop_reason='execution_failed', steps_count=1, final_feedback={'goal_score': 0.10}, trace={'events': []}))

    promoted = service.promote_best_for_scenario(scenario='Lead Gen', run_ids=['run-2', 'run-1'])
    assert promoted is not None
    assert promoted['scenario_governance']['scenario'] == 'Lead Gen'
    assert promoted['scenario_governance']['baseline_name'] == 'scenario:lead_gen:golden'
    assert promoted['scenario_governance']['selected_run_id'] == 'run-1'
    catalog_entry = service.scenario_catalog.get(scenario='Lead Gen')
    assert catalog_entry['scenario_governance']['baseline_name'] == 'scenario:lead_gen:golden'
