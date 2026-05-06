from runtime.inference.providers import (
    InferenceProviderAccelerationProfileCatalog,
    ProviderBatchExecutionPolicy,
    ProviderMemoryTransferPolicy,
)
from observability import InferenceAccelerationEvent, InferenceAccelerationLog


def test_inference_acceleration_exports_are_visible():
    assert InferenceProviderAccelerationProfileCatalog is not None
    assert ProviderBatchExecutionPolicy is not None
    assert ProviderMemoryTransferPolicy is not None
    assert InferenceAccelerationLog is not None
    assert InferenceAccelerationEvent is not None
