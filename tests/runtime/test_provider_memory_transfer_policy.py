from runtime.inference.providers.cpu_fallback_provider import CPUFallbackProvider
from runtime.inference.providers.local_gpu_provider import LocalGPUProvider
from runtime.inference.providers.provider_memory_transfer_policy import ProviderMemoryTransferPolicy


def test_provider_memory_transfer_policy_distinguishes_cpu_and_local_gpu():
    policy = ProviderMemoryTransferPolicy()

    cpu_plan = policy.plan(provider=CPUFallbackProvider())
    gpu_plan = policy.plan(provider=LocalGPUProvider())

    assert cpu_plan.transport_kind == 'in_process'
    assert cpu_plan.expected_overhead_ms == 0
    assert gpu_plan.transport_kind == 'pci_local'
    assert gpu_plan.expected_overhead_ms > cpu_plan.expected_overhead_ms
