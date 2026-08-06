from __future__ import annotations


class CrmBusinessMemoryAdapter:
    MEMORY_KEY = 'crm'

    def project(self, memory_state: dict[str, object], *, projection: dict[str, object]) -> dict[str, object]:
        payload = dict(memory_state)
        payload[self.MEMORY_KEY] = dict(projection)
        return payload
