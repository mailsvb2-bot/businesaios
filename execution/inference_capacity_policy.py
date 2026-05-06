from __future__ import annotations

from dataclasses import dataclass

from execution.inference_capacity_contract import InferenceCapacityTier


CANON_INFERENCE_CAPACITY_POLICY = True


@dataclass(frozen=True)
class InferenceCapacityPolicyContext:
    tenant_id: str | None
    distributed_network_enabled: bool
    premium_cloud_enabled: bool
    max_allowed_tier: InferenceCapacityTier


@dataclass(frozen=True)
class InferenceCapacityPolicy:
    def allows(self, ctx: InferenceCapacityPolicyContext, tier: InferenceCapacityTier) -> bool:
        if tier == InferenceCapacityTier.DISTRIBUTED_GPU_NETWORK and not ctx.distributed_network_enabled:
            return False
        if tier == InferenceCapacityTier.PREMIUM_EXTERNAL_CLOUD and not ctx.premium_cloud_enabled:
            return False
        ordered = list(InferenceCapacityTier)
        return ordered.index(tier) <= ordered.index(ctx.max_allowed_tier)
