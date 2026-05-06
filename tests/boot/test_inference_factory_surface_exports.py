from boot.factories import (
    build_inference_capacity_router,
    build_inference_dispatch_orchestrator,
    build_inference_provider_registry,
)


def test_inference_factory_exports_are_available_from_package_owner() -> None:
    registry = build_inference_provider_registry()
    router = build_inference_capacity_router(registry=registry)
    orchestrator = build_inference_dispatch_orchestrator(registry=registry, router=router)
    assert registry.names()
    assert router is not None
    assert orchestrator is not None
