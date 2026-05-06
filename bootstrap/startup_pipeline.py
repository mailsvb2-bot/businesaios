from __future__ import annotations

from dataclasses import dataclass

from bootstrap.app_boot_observability import AppBootObservability
from bootstrap.runtime_integration import RuntimeIntegration

CANON_STARTUP_PIPELINE_FINAL_OWNER = True
CANON_STARTUP_PIPELINE_INTEGRATION_ONLY = True
CANON_STARTUP_PIPELINE_NO_RUNTIME_ASSEMBLY = True


@dataclass
class StartupPipeline:
    runtime_integration: RuntimeIntegration
    observability: AppBootObservability

    def run(self) -> tuple[object, object, tuple[str, ...]]:
        self.observability.record("app_boot_started")
        built_runtime, application_service = self.runtime_integration.build()
        self.observability.record("runtime_integration_built")
        self.observability.record("app_boot_completed")
        return built_runtime, application_service, self.observability.events()
