from __future__ import annotations

from crm.crm_state_contract import CrmStateSlice


class CrmWorldStateAdapter:
    BRIDGE_KEY = 'crm'

    def enrich(self, world_state: dict[str, object], crm_state: CrmStateSlice) -> dict[str, object]:
        payload = dict(world_state)
        payload[self.BRIDGE_KEY] = {
            'provider_key': crm_state.provider_key,
            'funnel_health': crm_state.funnel_health,
            'open_deals': crm_state.open_deals,
            'stale_deals': crm_state.stale_deals,
            'recent_conversions': crm_state.recent_conversions,
            'signals': dict(crm_state.metadata),
        }
        return payload
