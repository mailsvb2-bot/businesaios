from execution.inference_capacity_contract import InferenceCapacityTier
from execution.inference_policy_guard import InferencePolicyEnvelope, InferencePolicyGuard


def test_inference_policy_guard_blocks_disabled_distributed_network():
    guard = InferencePolicyGuard()
    verdict = guard.evaluate(
        InferencePolicyEnvelope(
            tenant_id='tenant-a',
            requested_tier=InferenceCapacityTier.DISTRIBUTED_GPU_NETWORK,
            estimated_cost_usd=5.0,
            expected_benefit_usd=15.0,
            verification_mode='standard',
            distributed_network_enabled=False,
            premium_cloud_enabled=True,
        )
    )
    assert verdict.allowed is False
    assert 'distributed_network_disabled' in verdict.reason
