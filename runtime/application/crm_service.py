from __future__ import annotations

from crm.execution.crm_execution_service import CrmExecutionService
from crm.registry.crm_connector_registry import CrmConnectorRegistry
from crm.registry.crm_provider_registry import CrmProviderRegistry
from crm.registry.crm_registry_consistency import assert_crm_registry_consistency


class RuntimeCrmService:
    def __init__(
        self,
        execution_service: CrmExecutionService | None = None,
        *,
        connector_registry: CrmConnectorRegistry | None = None,
        provider_registry: CrmProviderRegistry | None = None,
    ) -> None:
        self._execution_service = execution_service or CrmExecutionService()
        self._connector_registry = connector_registry or CrmConnectorRegistry.build_default()
        self._provider_registry = provider_registry
        if self._provider_registry is not None:
            assert_crm_registry_consistency(self._provider_registry, self._connector_registry)

    @property
    def connector_registry(self) -> CrmConnectorRegistry:
        return self._connector_registry

    @property
    def provider_registry(self) -> CrmProviderRegistry | None:
        return self._provider_registry

    def connector_for(self, provider_key: str):
        if self._provider_registry is not None:
            self._provider_registry.get(provider_key)
        return self._connector_registry.get(provider_key)

    def execute(self, action, *, handler_map: dict[str, object]) -> dict[str, object]:
        return self._execution_service.execute(action, handler_map=handler_map)
