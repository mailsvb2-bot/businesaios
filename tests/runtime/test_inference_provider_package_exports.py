from runtime.inference.providers import (
    CPUFallbackProvider,
    InferenceProviderHealthMonitor,
    InferenceProviderRegistry,
    ProviderCircuitBreaker,
)


def test_runtime_inference_provider_package_exports() -> None:
    assert CPUFallbackProvider is not None
    assert InferenceProviderHealthMonitor is not None
    assert InferenceProviderRegistry is not None
    assert ProviderCircuitBreaker is not None
