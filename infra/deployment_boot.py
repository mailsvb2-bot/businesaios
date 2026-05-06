from __future__ import annotations

from dataclasses import dataclass

from infra.deployment_boot_result import DeploymentBootResult
from infra.idempotency import IdempotencyExecutor
from infra.idempotency_store import InMemoryIdempotencyStore
from infra.process_manager import ProcessManager
from infra.retry_models import RetryPolicySpec
from infra.retry_policy import RetryPolicy
from observability.metrics import InMemoryMetrics
from observability.metrics_exporter import MetricsExporter
from observability.structured_logging import StructuredLogger
from observability.trace_exporter import TraceExporter


@dataclass
class DeploymentBoot:
    def build(self) -> DeploymentBootResult:
        metrics = InMemoryMetrics()

        return DeploymentBootResult(
            process_manager=ProcessManager(
                logger=StructuredLogger("deployment.process_manager"),
            ),
            retry_policy=RetryPolicy(
                spec=RetryPolicySpec(
                    max_attempts=3,
                    delay_seconds=0.1,
                )
            ),
            idempotency=IdempotencyExecutor(
                store=InMemoryIdempotencyStore(),
            ),
            metrics_exporter=MetricsExporter(metrics=metrics),
            trace_exporter=TraceExporter(),
        )
