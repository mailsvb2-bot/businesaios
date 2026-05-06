from crm.crm_connector_contract import CrmConnector


def test_connector_implements_contract(hubspot_connector):
    assert isinstance(hubspot_connector, CrmConnector)
    assert hubspot_connector.capabilities().can_write_contacts is True
