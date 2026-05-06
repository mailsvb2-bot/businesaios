from execution.inference_capacity_contract import InferenceCapacityTier
from execution.inference_cold_start_policy import InferenceColdStartPolicy
from execution.inference_degradation_playbook import InferenceDegradationPlaybook


def test_inference_cold_start_policy_downgrades_high_tier_when_history_is_sparse():
    policy = InferenceColdStartPolicy()
    decision = policy.decide(historical_executions=0, requested_tier=InferenceCapacityTier.DISTRIBUTED_GPU_NETWORK)
    assert decision.preferred_tier == InferenceCapacityTier.LOCAL_GPU


def test_inference_degradation_playbook_handles_budget_pressure():
    playbook = InferenceDegradationPlaybook()
    decision = playbook.decide(current_tier=InferenceCapacityTier.PREMIUM_EXTERNAL_CLOUD, budget_pressure=True, provider_failure=False)
    assert decision.target_tier == InferenceCapacityTier.LOCAL_GPU
    assert decision.mode == 'budget_guarded_degradation'
