from runtime.bootstrap.runtime_builder import build_runtime


def test_registry_is_sealed_after_boot() -> None:
    registry, _ = build_runtime()
    snapshot = registry.snapshot()
    assert snapshot is not None
