from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from collections.abc import Mapping

from runtime.events import EventLog
from runtime.finance.event_publisher import FinanceEventPublisher
from runtime.finance.host_event_consumers import FinanceEventLogSink, FinanceEventReadModel, FinanceObservabilitySink
from runtime.finance.host_job_catalog import HostRuntimeJobCatalog
from runtime.finance.job_spec import FinanceJobSpec


@dataclass(frozen=True)
class FinanceHostRuntimeBinding:
    job_catalog: HostRuntimeJobCatalog
    event_log_sink: FinanceEventLogSink
    event_read_model: FinanceEventReadModel
    observability_sink: FinanceObservabilitySink


def bind_finance_into_host_runtime(
    *,
    event_log: EventLog,
    event_publisher: FinanceEventPublisher,
    namespace: str,
    jobs: Mapping[str, Callable[[dict], object]],
    specs: Mapping[str, FinanceJobSpec],
    orchestrator: object,
) -> FinanceHostRuntimeBinding:
    job_catalog = HostRuntimeJobCatalog()
    job_catalog.register_namespace(
        namespace=namespace,
        jobs=jobs,
        specs=specs,
        orchestrator=orchestrator,
    )
    event_log_sink = FinanceEventLogSink(event_log=event_log)
    event_read_model = FinanceEventReadModel()
    observability_sink = FinanceObservabilitySink()
    event_publisher.subscribe(event_log_sink.consume)
    event_publisher.subscribe(event_read_model.consume)
    event_publisher.subscribe(observability_sink.consume)
    return FinanceHostRuntimeBinding(
        job_catalog=job_catalog,
        event_log_sink=event_log_sink,
        event_read_model=event_read_model,
        observability_sink=observability_sink,
    )
