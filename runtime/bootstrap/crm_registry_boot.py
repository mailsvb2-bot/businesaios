from __future__ import annotations

from crm.registry.crm_provider_catalog import build_default_provider_catalog
from crm.registry.crm_provider_registry import CrmProviderRegistry


def build_crm_provider_registry() -> CrmProviderRegistry:
    return CrmProviderRegistry.from_catalog(build_default_provider_catalog())
