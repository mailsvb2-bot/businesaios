from boot.bootstrap_config_surface import build_bootstrap_config_surface
from boot.platform_boot_surface import build_platform_boot_surface


def test_platform_boot_surface_shares_runtime_observability_with_api_container() -> None:
    config = build_bootstrap_config_surface()
    platform = build_platform_boot_surface(config_surface=config)
    runtime_action = platform.runtime_surface.orchestrator.components.get("action_audit_log")
    runtime_decision = platform.runtime_surface.orchestrator.components.get("decision_audit_log")
    runtime_export = platform.runtime_surface.orchestrator.services.get("audit_export_service")

    assert platform.dependency_container.action_audit_log() is runtime_action
    assert platform.dependency_container.decision_audit_log() is runtime_decision
    assert platform.dependency_container.audit_export_service() is runtime_export
