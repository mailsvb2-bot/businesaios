from __future__ import annotations

from runtime.boot.finance_boot import build_finance_job_orchestrator, build_finance_job_registry, build_finance_job_specs, build_finance_runtime
from runtime.finance.host_runtime_integration import bind_finance_into_host_runtime
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from core.events.log import EventLog


def test_finance_jobs_register_into_host_runtime_catalog() -> None:
    runtime = build_finance_runtime()
    jobs = build_finance_job_registry()
    specs = build_finance_job_specs()
    orchestrator = build_finance_job_orchestrator(runtime, jobs)
    binding = bind_finance_into_host_runtime(
        event_log=EventLog(MemoryEventStore(), tenant='tenant-a'),
        event_publisher=runtime.event_publisher,
        namespace='finance',
        jobs=jobs,
        specs=specs,
        orchestrator=orchestrator,
    )

    assert binding.job_catalog.namespaces() == ('finance',)
    registration = binding.job_catalog.get('finance')
    assert sorted(registration.jobs) == sorted(jobs)
    assert registration.orchestrator is orchestrator
