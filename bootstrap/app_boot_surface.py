from __future__ import annotations

from dataclasses import dataclass

from bootstrap.app_boot_guard import validate_app_boot_result
from bootstrap.app_boot_observability import AppBootObservability
from bootstrap.app_boot_result import AppBootResult
from bootstrap.bootstrap_config_surface import BootstrapConfigSurface, build_bootstrap_config_surface
from bootstrap.runtime_integration import RuntimeIntegration
from bootstrap.startup_pipeline import StartupPipeline

CANON_APP_BOOT_SURFACE_FINAL_OWNER = True
CANON_APP_BOOT_SURFACE_NO_RUNTIME_ASSEMBLY = True


@dataclass(frozen=True)
class AppBootSurface:
    result: AppBootResult
    startup_events: tuple[str, ...]
    runtime_service_names: tuple[str, ...]
    config_surface: BootstrapConfigSurface

    def startup_snapshot(self) -> dict[str, object]:
        return {
            "events": self.startup_events,
            "runtime_services": self.runtime_service_names,
            "decision_application_type": type(self.result.decision_application).__name__,
            "config": self.config_surface.snapshot(),
        }


def build_app_boot_surface(
    *,
    runtime_integration: RuntimeIntegration | None = None,
    observability: AppBootObservability | None = None,
    config_surface: BootstrapConfigSurface | None = None,
) -> AppBootSurface:
    resolved_runtime_integration = runtime_integration or RuntimeIntegration()
    resolved_observability = observability or AppBootObservability()
    resolved_config_surface = config_surface or build_bootstrap_config_surface()
    pipeline = StartupPipeline(
        runtime_integration=resolved_runtime_integration,
        observability=resolved_observability,
    )
    built_runtime, application_service, startup_report = pipeline.run()
    result = AppBootResult(
        runtime=built_runtime,
        decision_application=application_service,
        startup_report=startup_report,
    )
    validate_app_boot_result(result)
    return AppBootSurface(
        result=result,
        startup_events=startup_report,
        runtime_service_names=built_runtime.report.service_names(),
        config_surface=resolved_config_surface,
    )


__all__ = ["AppBootSurface", "build_app_boot_surface"]
