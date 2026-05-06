from crm.registry.crm_connector_registry import CrmConnectorRegistry


def test_connector_registry_exposes_known_connectors() -> None:
    registry = CrmConnectorRegistry.build_default()
    assert registry.keys() == ('hubspot', 'pipedrive')
    assert registry.get('hubspot').provider.provider_key == 'hubspot'
    assert registry.get('pipedrive').provider.provider_key == 'pipedrive'
