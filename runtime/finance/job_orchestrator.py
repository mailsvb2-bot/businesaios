from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Mapping

if TYPE_CHECKING:
    from runtime.boot.finance_boot import StrategicFinanceRuntime
from runtime.tenancy import require_tenant_id
from runtime.finance.event_publisher import FinanceEventPublisher
from runtime.finance.job_spec import FinanceJobSpec


@dataclass(frozen=True)
class FinanceJobRunRecord:
    job_name: str
    correlation_id: str
    tenant_id: str
    touched_repositories: tuple[str, ...]


class FinanceJobOrchestrator:
    def __init__(
        self,
        *,
        runtime: "StrategicFinanceRuntime",
        job_registry: Mapping[str, Callable[[dict], object]],
        job_specs: Mapping[str, FinanceJobSpec],
        event_publisher: FinanceEventPublisher,
    ) -> None:
        self._runtime = runtime
        self._job_registry = dict(job_registry)
        self._job_specs = dict(job_specs)
        self._event_publisher = event_publisher
        self._records: list[FinanceJobRunRecord] = []

    def run(self, job_name: str, raw: dict) -> object:
        if job_name not in self._job_registry:
            raise KeyError(job_name)
        if job_name not in self._job_specs:
            raise KeyError(f"missing finance job spec for {job_name}")
        tenant_id = require_tenant_id(raw.get("tenant_id"))
        correlation_id = str(raw.get("correlation_id") or job_name)
        self._event_publisher.publish(
            "finance.job_started",
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            payload={"job_name": job_name, "runtime_phase": self._job_specs[job_name].runtime_phase},
        )
        result = self._job_registry[job_name](raw, runtime_provider=lambda: self._runtime)
        touched = self._touched_repositories(tenant_id, correlation_id)
        self._records.append(
            FinanceJobRunRecord(
                job_name=job_name,
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                touched_repositories=touched,
            )
        )
        self._event_publisher.publish(
            "finance.job_completed",
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            payload={"job_name": job_name, "touched_repositories": list(touched)},
        )
        return result

    def all_records(self) -> tuple[FinanceJobRunRecord, ...]:
        return tuple(self._records)

    def _touched_repositories(self, tenant_id: str, correlation_id: str) -> tuple[str, ...]:
        key = f"{tenant_id}:{correlation_id}"
        touched: list[str] = []
        if self._runtime.forecast_repository.get(key) is not None:
            touched.append("forecast_repository")
        if self._runtime.scenario_repository.get(key) is not None:
            touched.append("scenario_repository")
        if self._runtime.allocation_repository.get(key) is not None:
            touched.append("allocation_repository")
        if self._runtime.decision_audit_repository.get(key) is not None:
            touched.append("decision_audit_repository")
        return tuple(touched)
