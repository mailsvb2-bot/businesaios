from __future__ import annotations

from crm.memory.crm_business_memory_adapter import CrmBusinessMemoryAdapter


class RuntimeCrmMemoryAdapter:
    def __init__(self, adapter: CrmBusinessMemoryAdapter | None = None) -> None:
        self._adapter = adapter or CrmBusinessMemoryAdapter()

    def project(self, memory_state: dict[str, object], projection: dict[str, object]) -> dict[str, object]:
        return self._adapter.project(memory_state, projection=projection)
