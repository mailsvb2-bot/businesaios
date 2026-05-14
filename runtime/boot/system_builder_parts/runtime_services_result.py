from __future__ import annotations
CANON_BOOT_WIRING_ONLY = True

from dataclasses import dataclass, fields
from typing import Any

from runtime.runtime_infra import RuntimeInfra


@dataclass(frozen=True)
class RuntimeServicesResult(RuntimeInfra):
    decision_archive: Any = None
    event_log: Any = None
    archive: Any = None
    settings: Any = None
    FeatureFlags: Any = None
    composer: Any = None
    telegram_outbound_queue: Any = None
    pricing: Any = None
    tenant_id: Any = None
    preg: Any = None
    policy_selector: Any = None
    model_registry: Any = None
    finance_runtime: Any = None
    finance_job_registry: Any = None
    finance_event_registry: Any = None
    finance_job_specs: Any = None
    finance_job_orchestrator: Any = None
    host_job_catalog: Any = None
    finance_event_read_model: Any = None
    finance_observability: Any = None

    @property
    def runtime_infra(self) -> RuntimeInfra:
        payload = {field.name: getattr(self, field.name, None) for field in fields(RuntimeInfra)}
        return RuntimeInfra(**payload)

    def __getitem__(self, key: str):
        return getattr(self, str(key))
