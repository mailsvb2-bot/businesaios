from crm.crm_state_contract import CrmStateSlice
from crm.state.crm_world_state_adapter import CrmWorldStateAdapter


def test_world_state_adapter_uses_single_crm_bridge_key():
    state = CrmStateSlice(tenant_id='t', business_id='b', provider_key='hubspot')
    enriched = CrmWorldStateAdapter().enrich({}, state)
    assert list(enriched.keys()) == ['crm']
