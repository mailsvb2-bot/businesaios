from crm.registry.crm_provider_catalog import build_default_provider_catalog
from crm.registry.crm_provider_registry import CrmProviderRegistry


def test_provider_registry_is_explicit_source_of_truth():
    registry = CrmProviderRegistry.from_catalog(build_default_provider_catalog())
    assert sorted(registry.providers) == ['hubspot', 'pipedrive']
