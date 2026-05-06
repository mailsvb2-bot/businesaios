from __future__ import annotations

from dataclasses import dataclass

from infra.lifecycle import ApplicationLifecycle
from infra.shutdown_hooks import ShutdownHooks
from observability.structured_logging import StructuredLogger


@dataclass(frozen=True)
class GracefulShutdownCoordinator:
    lifecycle: ApplicationLifecycle
    hooks: ShutdownHooks
    logger: StructuredLogger

    def shutdown(self) -> None:
        self.lifecycle.mark_stopping()
        self.logger.info("application_shutdown_started")
        self.hooks.run_all()
        self.lifecycle.mark_stopped()
        self.logger.info("application_shutdown_completed")
