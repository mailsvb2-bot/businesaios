from crm.state.crm_world_state_adapter import CrmWorldStateAdapter


def test_world_state_bridge_key_is_single_and_canonical():
    assert CrmWorldStateAdapter.BRIDGE_KEY == 'crm'
