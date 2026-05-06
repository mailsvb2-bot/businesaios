from crm.registry.crm_provider_catalog import build_default_provider_catalog
from crm.registry.crm_provider_registry import CrmProviderRegistry
from crm.registry.crm_provider_selector import CrmProviderSelector


def test_provider_selector_prefers_fully_capable_provider():
    selector = CrmProviderSelector(CrmProviderRegistry.from_catalog(build_default_provider_catalog()))
    provider = selector.select(required_capabilities=('can_write_pipelines', 'can_verify_writes'))
    assert provider.provider_key == 'hubspot'
