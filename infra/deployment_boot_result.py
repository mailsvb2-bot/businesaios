from __future__ import annotations

from dataclasses import dataclass

from infra.idempotency import IdempotencyExecutor
from infra.process_manager import ProcessManager
from infra.retry_policy import RetryPolicy
from observability.metrics_exporter import MetricsExporter
from observability.trace_exporter import TraceExporter


@dataclass(frozen=True)
class DeploymentBootResult:
    process_manager: ProcessManager
    retry_policy: RetryPolicy
    idempotency: IdempotencyExecutor
    metrics_exporter: MetricsExporter
    trace_exporter: TraceExporter
