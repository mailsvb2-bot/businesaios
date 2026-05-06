from __future__ import annotations

from crm.registry.crm_capability_registry import CrmCapabilityRegistry


class CrmMaturityMatrix:
    def __init__(self, capability_registry: CrmCapabilityRegistry) -> None:
        self._capability_registry = capability_registry

    def production_ready(self, provider_key: str) -> bool:
        capability = self._capability_registry.for_provider(provider_key)
        return bool(
            capability.maturity == 'real'
            and capability.can_verify_writes
            and capability.supports_idempotency
        )
