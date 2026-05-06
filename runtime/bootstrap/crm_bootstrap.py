from __future__ import annotations

from crm.registry.crm_connector_registry import CrmConnectorRegistry
from crm.registry.crm_provider_registry import CrmProviderRegistry
from crm.registry.crm_registry_consistency import assert_crm_registry_consistency
from runtime.application.crm_service import RuntimeCrmService
from runtime.bootstrap.crm_connector_boot import build_crm_connector_registry
from runtime.bootstrap.crm_registry_boot import build_crm_provider_registry


def build_crm_service(
    connector_registry: CrmConnectorRegistry | None = None,
    provider_registry: CrmProviderRegistry | None = None,
) -> RuntimeCrmService:
    active_connector_registry = connector_registry or build_crm_connector_registry()
    active_provider_registry = provider_registry or build_crm_provider_registry()
    assert_crm_registry_consistency(active_provider_registry, active_connector_registry)
    return RuntimeCrmService(
        connector_registry=active_connector_registry,
        provider_registry=active_provider_registry,
    )
