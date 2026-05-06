from __future__ import annotations

from execution.inference_acceleration_contract import InferenceAccelerationProfile
from execution.inference_capacity_contract import InferenceCapacityTier


CANON_RUNTIME_INFERENCE_PROVIDER_ACCELERATION_PROFILE = True


class InferenceProviderAccelerationProfileCatalog:
    """Canonical owner of provider-tier acceleration metadata.

    This does not introduce a new routing brain. It only translates already-selected
    capacity tiers into stable runtime acceleration metadata.
    """

    def profile_for_tier(self, *, tier: InferenceCapacityTier) -> InferenceAccelerationProfile:
        if tier == InferenceCapacityTier.CPU_FALLBACK:
            return InferenceAccelerationProfile(
                tier=tier,
                execution_mode='synchronous',
                device_class='cpu',
                supports_batch_execution=False,
                prefers_local_memory=True,
                transport_kind='in_process',
                metadata={'acceleration_path': 'cpu_fallback'},
            )
        if tier == InferenceCapacityTier.LOCAL_GPU:
            return InferenceAccelerationProfile(
                tier=tier,
                execution_mode='accelerated',
                device_class='local_gpu',
                supports_batch_execution=True,
                prefers_local_memory=True,
                transport_kind='pci_local',
                metadata={'acceleration_path': 'local_gpu'},
            )
        if tier == InferenceCapacityTier.DEDICATED_GPU:
            return InferenceAccelerationProfile(
                tier=tier,
                execution_mode='accelerated',
                device_class='dedicated_gpu',
                supports_batch_execution=True,
                prefers_local_memory=False,
                transport_kind='dedicated_fabric',
                metadata={'acceleration_path': 'dedicated_gpu'},
            )
        if tier == InferenceCapacityTier.PRIVATE_GPU_POOL:
            return InferenceAccelerationProfile(
                tier=tier,
                execution_mode='pool_accelerated',
                device_class='private_gpu_pool',
                supports_batch_execution=True,
                prefers_local_memory=False,
                transport_kind='private_network',
                metadata={'acceleration_path': 'private_gpu_pool'},
            )
        if tier == InferenceCapacityTier.DISTRIBUTED_GPU_NETWORK:
            return InferenceAccelerationProfile(
                tier=tier,
                execution_mode='distributed_accelerated',
                device_class='distributed_gpu_network',
                supports_batch_execution=True,
                prefers_local_memory=False,
                transport_kind='distributed_network',
                metadata={'acceleration_path': 'distributed_gpu_network'},
            )
        return InferenceAccelerationProfile(
            tier=tier,
            execution_mode='external_accelerated',
            device_class='external_cloud',
            supports_batch_execution=True,
            prefers_local_memory=False,
            transport_kind='external_network',
            metadata={'acceleration_path': 'external_cloud'},
        )
