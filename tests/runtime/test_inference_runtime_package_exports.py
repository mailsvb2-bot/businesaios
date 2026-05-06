from runtime.inference import (
    InferenceCapacityManager,
    InferenceCapacityStateStore,
    InferenceProviderRegistry,
    LocalGPUProvider,
)


def test_runtime_inference_package_exports() -> None:
    assert InferenceCapacityManager is not None
    assert InferenceCapacityStateStore is not None
    assert InferenceProviderRegistry is not None
    assert LocalGPUProvider is not None
