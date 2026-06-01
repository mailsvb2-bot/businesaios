from __future__ import annotations

from execution.inference_acceleration_contract import InferenceBatchPlan
from execution.inference_provider_contract import InferenceProvider

CANON_RUNTIME_INFERENCE_PROVIDER_BATCH_EXECUTION_POLICY = True


class ProviderBatchExecutionPolicy:
    """Canonical owner of runtime batch sizing for already-selected providers."""

    def plan(self, *, provider: InferenceProvider, requested_batch_items: int) -> InferenceBatchPlan:
        requested = max(int(requested_batch_items), 1)
        allowed = max(int(provider.profile.limits.max_batch_items), 1)
        batch_items = min(requested, allowed)
        reason = 'provider max_batch_items enforced' if requested > allowed else 'provider batch accepted'
        return InferenceBatchPlan(
            provider_name=provider.name,
            tier=provider.profile.tier,
            batch_items=batch_items,
            reason=reason,
        )
