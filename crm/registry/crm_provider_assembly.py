from __future__ import annotations

from dataclasses import dataclass

from crm.registry.crm_connector_registry import CrmConnectorRegistry
from crm.registry.crm_provider_definition import (
    CrmProviderDefinition,
    merge_provider_definitions,
)
from crm.registry.crm_provider_definitions import build_default_crm_provider_definitions
from crm.registry.crm_provider_registry import CrmProviderRegistry
from crm.registry.crm_registry_consistency import assert_crm_registry_consistency


@dataclass(frozen=True)
class CrmProviderAssembly:
    """Build planning and execution registries from one provider definition set.

    This is the preferred composition boundary for deployments that add CRM
    adapters. A definition can use a closure as its connector factory, so
    deployment-specific credentials/token stores may be injected without
    changing provider selection, decision, or execution code.
    """

    definitions: tuple[CrmProviderDefinition, ...]

    @classmethod
    def build_default(
        cls,
        *,
        extra_definitions: tuple[CrmProviderDefinition, ...] = (),
    ) -> CrmProviderAssembly:
        return cls(
            definitions=merge_provider_definitions(
                build_default_crm_provider_definitions(),
                extra_definitions,
            )
        )

    @classmethod
    def from_definitions(
        cls,
        definitions: tuple[CrmProviderDefinition, ...],
    ) -> CrmProviderAssembly:
        return cls(definitions=merge_provider_definitions((), definitions))

    def build_provider_registry(self) -> CrmProviderRegistry:
        return CrmProviderRegistry.from_catalog(
            tuple(definition.build_provider() for definition in self.definitions)
        )

    def build_connector_registry(self) -> CrmConnectorRegistry:
        return CrmConnectorRegistry.from_definitions(self.definitions)

    def build_registries(self) -> tuple[CrmProviderRegistry, CrmConnectorRegistry]:
        provider_registry = self.build_provider_registry()
        connector_registry = self.build_connector_registry()
        assert_crm_registry_consistency(provider_registry, connector_registry)
        return provider_registry, connector_registry


__all__ = ['CrmProviderAssembly']
