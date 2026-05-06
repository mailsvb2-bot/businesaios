from __future__ import annotations

from crm.state.crm_world_state_adapter import CrmWorldStateAdapter


class CrmWorldStateEnricher:
    def __init__(self, adapter: CrmWorldStateAdapter | None = None) -> None:
        self._adapter = adapter or CrmWorldStateAdapter()

    def enrich(self, world_state: dict[str, object], crm_state) -> dict[str, object]:
        return self._adapter.enrich(world_state, crm_state)
