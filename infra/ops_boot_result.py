from __future__ import annotations

from dataclasses import dataclass

from infra.background_jobs import BackgroundJobs
from infra.graceful_shutdown import GracefulShutdownCoordinator
from infra.lifecycle import ApplicationLifecycle
from observability.telemetry_bundle import TelemetryBundle


@dataclass(frozen=True)
class OpsBootResult:
    lifecycle: ApplicationLifecycle
    shutdown: GracefulShutdownCoordinator
    background_jobs: BackgroundJobs
    telemetry: TelemetryBundle
