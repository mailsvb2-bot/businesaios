from __future__ import annotations

from execution.inference_acceleration_contract import InferenceMemoryTransferPlan
from execution.inference_provider_contract import InferenceProvider
from runtime.inference.providers.provider_acceleration_profile import InferenceProviderAccelerationProfileCatalog


CANON_RUNTIME_INFERENCE_PROVIDER_MEMORY_TRANSFER_POLICY = True


class ProviderMemoryTransferPolicy:
    """Canonical owner of transfer-path metadata for selected inference providers."""

    _OVERHEAD_BY_TRANSPORT = {
        'in_process': 0,
        'pci_local': 2,
        'dedicated_fabric': 6,
        'private_network': 18,
        'distributed_network': 35,
        'external_network': 60,
    }

    def __init__(self, *, catalog: InferenceProviderAccelerationProfileCatalog | None = None) -> None:
        self._catalog = catalog or InferenceProviderAccelerationProfileCatalog()

    def plan(self, *, provider: InferenceProvider) -> InferenceMemoryTransferPlan:
        profile = self._catalog.profile_for_tier(tier=provider.profile.tier)
        overhead = self._OVERHEAD_BY_TRANSPORT.get(profile.transport_kind, 25)
        return InferenceMemoryTransferPlan(
            provider_name=provider.name,
            tier=provider.profile.tier,
            transport_kind=profile.transport_kind,
            expected_overhead_ms=overhead,
            reason=f'transport derived from tier {provider.profile.tier.value}',
        )
