from __future__ import annotations

from execution.inference_provider_contract import InferenceProvider, InferenceProviderHealth


CANON_RUNTIME_INFERENCE_PROVIDER_HEALTH_MONITOR = True


class InferenceProviderHealthMonitor:
    def __init__(self, *, providers: dict[str, InferenceProvider]) -> None:
        self._providers = dict(providers)

    def snapshots(self) -> list[InferenceProviderHealth]:
        return [provider.health() for provider in self._providers.values()]

    def floor_score(self) -> float:
        snapshots = self.snapshots()
        if not snapshots:
            return 0.0
        return min(item.availability_score * (1.0 - item.error_rate) for item in snapshots)
