from runtime.inference.providers.local_gpu_provider import LocalGPUProvider
from runtime.inference.providers.provider_batch_execution_policy import ProviderBatchExecutionPolicy


def test_provider_batch_execution_policy_caps_to_provider_limit():
    policy = ProviderBatchExecutionPolicy()
    provider = LocalGPUProvider()

    plan = policy.plan(provider=provider, requested_batch_items=999)

    assert plan.provider_name == provider.name
    assert plan.batch_items == provider.profile.limits.max_batch_items
    assert 'enforced' in plan.reason
