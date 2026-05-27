import pytest

from crm.registry.crm_provider_catalog import build_default_provider_catalog
from crm.registry.crm_provider_registry import CrmProviderRegistry
from crm.registry.crm_provider_selector import CrmProviderSelector


def test_provider_selection_fails_closed_for_missing_capability():
    selector = CrmProviderSelector(CrmProviderRegistry.from_catalog(build_default_provider_catalog()))
    with pytest.raises(LookupError):
        selector.select(required_capabilities=('nonexistent_capability',))
