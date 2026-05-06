from __future__ import annotations

from crm.memory.crm_memory_projection import CrmMemoryProjection


class CrmBusinessMemoryAdapter:
    MEMORY_KEY = 'crm'

    def project(self, memory_state: dict[str, object], *, projection: dict[str, object]) -> dict[str, object]:
        payload = dict(memory_state)
        payload[self.MEMORY_KEY] = dict(projection)
        return payload
