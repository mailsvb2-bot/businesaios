from runtime.bootstrap.runtime_builder import build_runtime
from runtime.service_names import RuntimeServiceName


def test_runtime_contains_observability_service() -> None:
    registry, _ = build_runtime()
    assert registry.has(RuntimeServiceName.OBSERVABILITY)
