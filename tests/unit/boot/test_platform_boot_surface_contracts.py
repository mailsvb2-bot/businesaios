from boot.bootstrap_config_surface import build_bootstrap_config_surface
from boot.observability_boot import build_observability_surface
from boot.platform_boot_surface import build_platform_boot_surface
from boot.system_boot_surface import build_system_boot_surface


def test_platform_boot_surface_reuses_single_config_surface() -> None:
    config = build_bootstrap_config_surface()
    platform = build_platform_boot_surface(config_surface=config)
    assert platform.config_surface is config
    assert platform.system_surface.config_surface is config
    assert platform.runtime_surface.config_surface is config
    assert platform.dependency_container.config_surface is config


def test_platform_boot_surface_matches_explicit_system_surface_result() -> None:
    config = build_bootstrap_config_surface()
    system = build_system_boot_surface(config_surface=config)
    platform = build_platform_boot_surface(config_surface=config)
    assert type(platform.result) is type(system.result)
    assert type(platform.http_app).__name__ == type(system.http_app).__name__


def test_platform_boot_surface_threads_configured_trace_paths() -> None:
    config = build_bootstrap_config_surface()
    platform = build_platform_boot_surface(config_surface=config)
    observability = build_observability_surface(config_surface=platform.config_surface)
    execution_store = observability.components["execution_trace_store"]
    decision_store = observability.components["decision_trace_store"]
    effect_store = observability.components["runtime_effect_trace_store"]
    if hasattr(execution_store, "path"):
        assert str(execution_store.path) == str(config.execution_trace_store_path)
        assert str(decision_store.path) == str(config.decision_trace_store_path)
        assert str(effect_store.path) == str(config.runtime_effect_trace_store_path)


def test_platform_boot_surface_shares_runtime_observability_with_api_container() -> None:
    config = build_bootstrap_config_surface()
    platform = build_platform_boot_surface(config_surface=config)
    runtime_action = platform.runtime_surface.orchestrator.components.get("action_audit_log")
    runtime_decision = platform.runtime_surface.orchestrator.components.get("decision_audit_log")
    runtime_export = platform.runtime_surface.orchestrator.services.get("audit_export_service")

    assert platform.dependency_container.action_audit_log() is runtime_action
    assert platform.dependency_container.decision_audit_log() is runtime_decision
    assert platform.dependency_container.audit_export_service() is runtime_export
