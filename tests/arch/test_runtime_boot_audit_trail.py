from runtime.bootstrap.runtime_builder import build_runtime
from runtime.service_names import RuntimeServiceName


def test_runtime_boot_produces_audit_trail() -> None:
    registry, _ = build_runtime()
    observability = registry.get(RuntimeServiceName.OBSERVABILITY)

    event_names = observability.audit_log.event_names()

    assert "runtime_boot_started" in event_names
    assert "runtime_manifest_loaded" in event_names
    assert "runtime_manifest_validated" in event_names
    assert "runtime_boot_validated" in event_names
    assert "runtime_registry_sealed" in event_names
