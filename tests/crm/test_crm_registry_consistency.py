from crm.registry.crm_connector_registry import CrmConnectorRegistry
from crm.registry.crm_provider_catalog import build_default_provider_catalog
from crm.registry.crm_provider_registry import CrmProviderRegistry
from crm.registry.crm_registry_consistency import assert_crm_registry_consistency


def test_provider_and_connector_registries_are_consistent() -> None:
    provider_registry = CrmProviderRegistry.from_catalog(build_default_provider_catalog())
    connector_registry = CrmConnectorRegistry.build_default()
    assert_crm_registry_consistency(provider_registry, connector_registry) is None
