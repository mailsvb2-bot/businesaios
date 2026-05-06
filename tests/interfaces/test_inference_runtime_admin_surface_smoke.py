from interfaces.api import (
    InferenceAdminRouteHandlers,
    InferenceCapacityRouteHandlers,
    InferenceProviderRouteHandlers,
    InferenceRuntimeAdminRouteHandlers,
)
from entrypoints.api import (
    InferenceAdminRouteHandlers as EntrypointInferenceAdminRouteHandlers,
    InferenceCapacityRouteHandlers as EntrypointInferenceCapacityRouteHandlers,
    InferenceProviderRouteHandlers as EntrypointInferenceProviderRouteHandlers,
    InferenceRuntimeAdminRouteHandlers as EntrypointInferenceRuntimeAdminRouteHandlers,
)


def test_inference_api_surfaces_are_importable_from_package_roots() -> None:
    assert InferenceCapacityRouteHandlers is not None
    assert InferenceProviderRouteHandlers is not None
    assert InferenceAdminRouteHandlers is not None
    assert InferenceRuntimeAdminRouteHandlers is not None
    assert EntrypointInferenceCapacityRouteHandlers is not None
    assert EntrypointInferenceProviderRouteHandlers is not None
    assert EntrypointInferenceAdminRouteHandlers is not None
    assert EntrypointInferenceRuntimeAdminRouteHandlers is not None
