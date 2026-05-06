from runtime.inference.provisioning import (
    InferenceCapacityManager,
    InferenceCapacityState,
    InferenceCapacityStateStore,
    InferenceUpgradeCooldownTracker,
)


def test_runtime_inference_provisioning_package_exports() -> None:
    assert InferenceCapacityManager is not None
    assert InferenceCapacityState is not None
    assert InferenceCapacityStateStore is not None
    assert InferenceUpgradeCooldownTracker is not None
