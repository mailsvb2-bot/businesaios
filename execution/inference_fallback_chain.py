from __future__ import annotations

from execution.inference_capacity_contract import InferenceCapacityTier


CANON_INFERENCE_FALLBACK_CHAIN = True


class InferenceFallbackChain:
    _ORDER = (
        InferenceCapacityTier.LOCAL_GPU,
        InferenceCapacityTier.DEDICATED_GPU,
        InferenceCapacityTier.PRIVATE_GPU_POOL,
        InferenceCapacityTier.DISTRIBUTED_GPU_NETWORK,
        InferenceCapacityTier.PREMIUM_EXTERNAL_CLOUD,
        InferenceCapacityTier.CPU_FALLBACK,
    )

    def ordered_tiers_from(self, tier: InferenceCapacityTier) -> tuple[InferenceCapacityTier, ...]:
        if tier not in self._ORDER:
            return self._ORDER
        start = self._ORDER.index(tier)
        return self._ORDER[start:]

    def failover_tiers(self, tier: InferenceCapacityTier) -> tuple[InferenceCapacityTier, ...]:
        ordered = self.ordered_tiers_from(tier)
        return ordered[1:] if len(ordered) > 1 else (InferenceCapacityTier.CPU_FALLBACK,)

    def failover_tier(self, tier: InferenceCapacityTier) -> InferenceCapacityTier:
        fallbacks = self.failover_tiers(tier)
        return fallbacks[0] if fallbacks else InferenceCapacityTier.CPU_FALLBACK
