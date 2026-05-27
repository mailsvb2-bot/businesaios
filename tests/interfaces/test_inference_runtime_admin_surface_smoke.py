from entrypoints.api import (
    InferenceAdminRouteHandlers as EntrypointInferenceAdminRouteHandlers,
)
from entrypoints.api import (
    InferenceCapacityRouteHandlers as EntrypointInferenceCapacityRouteHandlers,
)
from entrypoints.api import (
    InferenceProviderRouteHandlers as EntrypointInferenceProviderRouteHandlers,
)
from entrypoints.api import (
    InferenceRuntimeAdminRouteHandlers as EntrypointInferenceRuntimeAdminRouteHandlers,
)
from interfaces.api import (
    InferenceAdminRouteHandlers,
    InferenceCapacityRouteHandlers,
    InferenceProviderRouteHandlers,
    InferenceRuntimeAdminRouteHandlers,
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
