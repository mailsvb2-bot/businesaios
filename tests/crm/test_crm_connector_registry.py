from crm.registry.crm_connector_registry import CrmConnectorRegistry


def test_connector_registry_exposes_known_connectors() -> None:
    registry = CrmConnectorRegistry.build_default()
    expected = ('amocrm', 'bitrix24', 'hubspot', 'pipedrive', 'salesforce')

    assert registry.keys() == expected
    for provider_key in expected:
        assert registry.get(provider_key).provider.provider_key == provider_key
