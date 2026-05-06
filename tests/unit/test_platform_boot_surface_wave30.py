from boot.bootstrap_config_surface import build_bootstrap_config_surface
from boot.observability_boot import build_observability_surface
from boot.platform_boot_surface import build_platform_boot_surface


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
