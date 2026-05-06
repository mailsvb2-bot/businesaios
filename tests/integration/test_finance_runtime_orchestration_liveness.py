from __future__ import annotations

from runtime.boot.finance_boot import build_finance_job_orchestrator, build_finance_runtime
from tests.test_finance_canon_integration_v27 import _snapshot


RAW = {
    'tenant_id': 'tenant-live',
    'correlation_id': 'corr-live',
    'economics_snapshot': _snapshot(),
}


def test_finance_job_orchestrator_runs_host_job_lifecycle() -> None:
    runtime = build_finance_runtime()
    orchestrator = build_finance_job_orchestrator(runtime)

    result = orchestrator.run('finance.run_scenario_evaluation', RAW)

    assert result['selected_scenario']
    records = orchestrator.all_records()
    assert records
    assert records[-1].job_name == 'finance.run_scenario_evaluation'
    assert 'decision_audit_repository' in records[-1].touched_repositories
    event_names = [item.event_name for item in runtime.event_publisher.all()]
    assert 'finance.job_started' in event_names
    assert 'finance.job_completed' in event_names
    assert 'finance.forecast_revised' in event_names
    assert 'finance.scenario_selected' in event_names
    assert 'finance.allocation_recommended' in event_names


def test_finance_repositories_are_live_after_orchestrated_job() -> None:
    runtime = build_finance_runtime()
    orchestrator = build_finance_job_orchestrator(runtime)

    orchestrator.run('finance.run_forecast', RAW)

    key = 'tenant-live:corr-live'
    assert runtime.forecast_repository.get(key) is not None
    assert runtime.scenario_repository.get(key) is not None
    assert runtime.allocation_repository.get(key) is not None
    assert runtime.decision_audit_repository.get(key) is not None
