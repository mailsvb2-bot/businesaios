"""Finance boot facade. Composes runtime, registry, attach, routes."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable
from collections.abc import MutableMapping

from runtime.boot.finance_boot_registry import (
    build_finance_job_specs,
    register_finance_events,
    register_finance_jobs,
)
from runtime.boot.finance_boot_runtime import StrategicFinanceRuntime, build_finance_runtime

# Re-export for backward compatibility
__all__ = [
    "attach_finance_host_runtime",
    "attach_finance_runtime",
    "build_finance_event_registry",
    "build_finance_job_orchestrator",
    "build_finance_job_registry",
    "build_finance_job_specs",
    "build_finance_runtime",
    "register_finance_events",
    "register_finance_jobs",
    "register_finance_routes",
    "register_finance_runtime",
    "StrategicFinanceRuntime",
]
from runtime.finance.host_runtime_integration import FinanceHostRuntimeBinding
from runtime.finance.job_orchestrator import FinanceJobOrchestrator

CANON_BOOT_WIRING_ONLY = True
# StrategicFinanceService is built in runtime finance runtime factory.


def register_finance_runtime(
    host_runtime_provider: Callable[[], StrategicFinanceRuntime] | None = None,
) -> StrategicFinanceRuntime:
    runtime = host_runtime_provider() if host_runtime_provider is not None else build_finance_runtime()
    if not isinstance(runtime, StrategicFinanceRuntime):
        raise TypeError("finance runtime provider must return StrategicFinanceRuntime")
    return runtime


def build_finance_job_registry() -> dict[str, Callable[[dict], object]]:
    registry: dict[str, Callable[[dict], object]] = {}
    return register_finance_jobs(registry)


def build_finance_event_registry() -> dict[str, type[object]]:
    registry: dict[str, type[object]] = {}
    return register_finance_events(registry)


def build_finance_job_orchestrator(
    runtime: StrategicFinanceRuntime | None = None,
    job_registry: dict[str, Callable[[dict], object]] | None = None,
) -> FinanceJobOrchestrator:
    attached_runtime = runtime or build_finance_runtime()
    attached_registry = job_registry or build_finance_job_registry()
    return FinanceJobOrchestrator(
        runtime=attached_runtime,
        job_registry=attached_registry,
        job_specs=build_finance_job_specs(),
        event_publisher=attached_runtime.event_publisher,
    )


def _attach_mapping(
    target: MutableMapping[str, Any],
    runtime: StrategicFinanceRuntime,
    jobs: dict[str, Callable[[dict], object]],
    events: dict[str, type[object]],
    orchestrator: FinanceJobOrchestrator,
) -> MutableMapping[str, Any]:
    target["finance_runtime"] = runtime
    target["finance_job_registry"] = jobs
    target["finance_event_registry"] = events
    target["finance_job_specs"] = build_finance_job_specs()
    target["finance_job_orchestrator"] = orchestrator
    return target


def attach_finance_runtime(target: object, runtime: StrategicFinanceRuntime | None = None) -> object:
    attached_runtime = runtime or build_finance_runtime()
    jobs = build_finance_job_registry()
    events = build_finance_event_registry()
    orchestrator = build_finance_job_orchestrator(attached_runtime, jobs)

    if isinstance(target, MutableMapping):
        return _attach_mapping(target, attached_runtime, jobs, events, orchestrator)

    state = getattr(target, "state", None)
    if state is None:
        state = SimpleNamespace()
        setattr(target, "state", state)
    setattr(state, "finance_runtime", attached_runtime)
    setattr(state, "finance_job_registry", jobs)
    setattr(state, "finance_event_registry", events)
    setattr(state, "finance_job_specs", build_finance_job_specs())
    setattr(state, "finance_job_orchestrator", orchestrator)
    return target


def attach_finance_host_runtime(target: object, *, host_binding: FinanceHostRuntimeBinding) -> object:
    if isinstance(target, MutableMapping):
        target["host_job_catalog"] = host_binding.job_catalog
        target["finance_event_read_model"] = host_binding.event_read_model
        target["finance_observability"] = host_binding.observability_sink
        return target
    state = getattr(target, "state", None)
    if state is None:
        state = SimpleNamespace()
        setattr(target, "state", state)
    setattr(state, "host_job_catalog", host_binding.job_catalog)
    setattr(state, "finance_event_read_model", host_binding.event_read_model)
    setattr(state, "finance_observability", host_binding.observability_sink)
    return target


def register_finance_routes(app: object) -> object:
    return attach_finance_runtime(app)
