from crm.registry.crm_capability_registry import CrmCapabilityRegistry
from crm.registry.crm_provider_catalog import build_default_provider_catalog
from crm.registry.crm_provider_registry import CrmProviderRegistry


def test_capability_registry_lists_supported_providers():
    registry = CrmCapabilityRegistry(CrmProviderRegistry.from_catalog(build_default_provider_catalog()))
    assert 'hubspot' in registry.providers_supporting('can_write_contacts')
