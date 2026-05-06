from __future__ import annotations

from runtime.boot.finance_boot import (
    build_finance_event_registry,
    build_finance_job_orchestrator,
    build_finance_job_registry,
    build_finance_job_specs,
    build_finance_runtime,
)
from runtime.finance.host_runtime_integration import bind_finance_into_host_runtime

CANON_BOOT_WIRING_ONLY = True


def build_finance_bundle(*, event_log):
    finance_runtime = build_finance_runtime()
    finance_job_registry = build_finance_job_registry()
    finance_event_registry = build_finance_event_registry()
    finance_job_specs = build_finance_job_specs()
    finance_job_orchestrator = build_finance_job_orchestrator(finance_runtime, finance_job_registry)
    finance_host_binding = bind_finance_into_host_runtime(
        event_log=event_log,
        event_publisher=finance_runtime.event_publisher,
        namespace="finance",
        jobs=finance_job_registry,
        specs=finance_job_specs,
        orchestrator=finance_job_orchestrator,
    )
    return {
        "finance_runtime": finance_runtime,
        "finance_job_registry": finance_job_registry,
        "finance_event_registry": finance_event_registry,
        "finance_job_specs": finance_job_specs,
        "finance_job_orchestrator": finance_job_orchestrator,
        "finance_host_binding": finance_host_binding,
    }
