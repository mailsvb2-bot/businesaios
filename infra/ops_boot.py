from __future__ import annotations

from dataclasses import dataclass

from infra.background_jobs import BackgroundJobs
from infra.graceful_shutdown import GracefulShutdownCoordinator
from infra.lifecycle import ApplicationLifecycle
from infra.ops_boot_result import OpsBootResult
from infra.shutdown_hooks import ShutdownHooks
from observability.metrics import InMemoryMetrics
from observability.structured_logging import StructuredLogger
from observability.telemetry_bundle import TelemetryBundle


@dataclass
class OpsBoot:
    def build(self) -> OpsBootResult:
        lifecycle = ApplicationLifecycle()
        logger = StructuredLogger("ops")
        metrics = InMemoryMetrics()
        telemetry = TelemetryBundle(
            logger=logger,
            metrics=metrics,
        )

        hooks = ShutdownHooks()
        background_jobs = BackgroundJobs(
            logger=StructuredLogger("background_jobs"),
        )
        shutdown = GracefulShutdownCoordinator(
            lifecycle=lifecycle,
            hooks=hooks,
            logger=logger,
        )

        return OpsBootResult(
            lifecycle=lifecycle,
            shutdown=shutdown,
            background_jobs=background_jobs,
            telemetry=telemetry,
        )
