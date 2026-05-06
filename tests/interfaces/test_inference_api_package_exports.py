from interfaces.api import (
    InferenceAdminRouteHandlers,
    InferenceCapacityRouteHandlers,
    InferenceProviderRouteHandlers,
    InferenceRuntimeAdminRouteHandlers,
)


def test_interfaces_api_exports_inference_handlers() -> None:
    assert InferenceAdminRouteHandlers is not None
    assert InferenceCapacityRouteHandlers is not None
    assert InferenceProviderRouteHandlers is not None
    assert InferenceRuntimeAdminRouteHandlers is not None
