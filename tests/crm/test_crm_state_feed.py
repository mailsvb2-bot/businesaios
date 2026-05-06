from crm.state.crm_state_feed import CrmStateFeed


def test_state_feed_builds_snapshot(hubspot_connector, connection):
    snapshot = CrmStateFeed().fetch(hubspot_connector, connection)
    assert snapshot.provider_key == 'hubspot'
