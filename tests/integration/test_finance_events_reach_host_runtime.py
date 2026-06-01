from __future__ import annotations

from core.events.log import EventLog
from runtime.boot.finance_boot import (
    build_finance_job_orchestrator,
    build_finance_job_registry,
    build_finance_job_specs,
    build_finance_runtime,
)
from runtime.finance.host_runtime_integration import bind_finance_into_host_runtime
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def test_finance_events_flow_into_host_event_log_and_observability() -> None:
    store = MemoryEventStore()
    event_log = EventLog(store, tenant='tenant-a')
    runtime = build_finance_runtime()
    jobs = build_finance_job_registry()
    orchestrator = build_finance_job_orchestrator(runtime, jobs)
    binding = bind_finance_into_host_runtime(
        event_log=event_log,
        event_publisher=runtime.event_publisher,
        namespace='finance',
        jobs=jobs,
        specs=build_finance_job_specs(),
        orchestrator=orchestrator,
    )

    payload = {
        'tenant_id': 'tenant-a',
        'correlation_id': 'corr-1',
        'period_months': 6,
        'revenue': '1000',
        'costs': '600',
        'cash': '500',
        'debt': '0',
        'customers': 100,
        'new_customers': 10,
        'channel_spend': {'marketing': '200', 'sales': '100'},
        'channel_new_customers': {'marketing': 7, 'sales': 3},
        'assumptions': {'contribution_margin_ratio': '0.40'},
    }
    orchestrator.run('finance.run_forecast', payload)

    assert binding.event_log_sink.count >= 3
    assert 'finance.job_completed' in binding.observability_sink.counters()
    correlation_events = binding.observability_sink.correlation_events('tenant-a', 'corr-1')
    assert 'finance.forecast_revised' in correlation_events
    assert binding.event_read_model.all()
    assert any(item.get('event_type') == 'finance.forecast_revised' for item in list(store))
