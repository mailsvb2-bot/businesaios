from execution.inference_capacity_contract import InferenceCapacityTier
from execution.inference_fallback_chain import InferenceFallbackChain


def test_fallback_chain_does_not_cycle_back_to_stronger_tiers():
    chain = InferenceFallbackChain()
    assert chain.ordered_tiers_from(InferenceCapacityTier.DEDICATED_GPU) == (
        InferenceCapacityTier.DEDICATED_GPU,
        InferenceCapacityTier.PRIVATE_GPU_POOL,
        InferenceCapacityTier.DISTRIBUTED_GPU_NETWORK,
        InferenceCapacityTier.PREMIUM_EXTERNAL_CLOUD,
        InferenceCapacityTier.CPU_FALLBACK,
    )
    assert chain.failover_tiers(InferenceCapacityTier.CPU_FALLBACK) == (InferenceCapacityTier.CPU_FALLBACK,)
