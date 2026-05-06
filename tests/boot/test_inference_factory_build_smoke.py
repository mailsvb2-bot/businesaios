from boot.factories import (
    build_inference_capacity_router,
    build_inference_dispatch_orchestrator,
    build_inference_provider_registry,
)


def test_inference_factories_build_together() -> None:
    registry = build_inference_provider_registry()
    router = build_inference_capacity_router(registry=registry)
    orchestrator = build_inference_dispatch_orchestrator(registry=registry, router=router)
    assert registry.names()
    assert orchestrator is not None
