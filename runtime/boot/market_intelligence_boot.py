from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from execution.market_intelligence_loop import MarketIntelligenceLoop
from execution.market_intelligence_orchestration import MarketIntelligenceOrchestration, SyncSchedule
from execution.market_intelligence_scheduler_service import MarketIntelligenceSchedulerService
from execution.market_intelligence_scheduler_supervisor import MarketIntelligenceSchedulerSupervisor
from reliability.distributed_lock import DistributedLock, build_distributed_lock
from runtime.executor_runtime_support import RuntimeExecutorRecoverySupport
from runtime.market_intelligence_runtime_registry_bridge import attach_market_intelligence_runtime_to_registry, MarketIntelligenceRuntimeAttachmentReport
from runtime.market_intelligence_runtime_support import build_market_intelligence_runtime_support
from runtime.runtime_observability import RuntimeObservability
from runtime.managed_runtime_plane import ManagedRuntimePlane
from runtime.service_names import RuntimeServiceName


CANON_BOOT_WIRING_ONLY = True
CANON_MARKET_INTELLIGENCE_BOOT = True


@dataclass
class MarketIntelligenceRuntime:
    loop: MarketIntelligenceLoop
    scheduler: MarketIntelligenceSchedulerService
    supervisor: MarketIntelligenceSchedulerSupervisor
    attachment_report: MarketIntelligenceRuntimeAttachmentReport | None = None

    def start(self) -> None:
        self.supervisor.start()

    def pulse_once(self) -> tuple[dict[str, Any], ...]:
        return self.supervisor.pulse_once()

    def request_stop(self, *, reason: str = 'market_intelligence_runtime_stop') -> None:
        self.supervisor.request_stop(reason=reason)

    def join(self, *, timeout_seconds: float = 10.0):
        return self.supervisor.join(timeout_seconds=timeout_seconds)

    def snapshot(self) -> dict[str, object]:
        return {
            'scheduler': self.scheduler.snapshot(),
            'supervisor': self.supervisor.snapshot().__dict__,
            'operator': self.loop.operator_control.snapshot(),
            'compliance': self.loop.compliance.store.snapshot(),
            'observability': self.loop.observability_store.snapshot(),
            'attachment_report': (self.attachment_report.__dict__ if self.attachment_report is not None else None),
        }


@dataclass
class MarketIntelligenceBoot:
    execute_action: Callable[[str, Mapping[str, Any]], Mapping[str, Any]]
    orchestration: MarketIntelligenceOrchestration = field(default_factory=MarketIntelligenceOrchestration)
    distributed_lock: DistributedLock | None = None
    runtime_infra: Any | None = None
    recovery_support: RuntimeExecutorRecoverySupport | None = None
    outbox: Any | None = None
    runtime_registry: Any | None = None
    runtime_observability: RuntimeObservability | None = None
    managed_runtime_plane: ManagedRuntimePlane | None = None

    def build(self) -> MarketIntelligenceRuntime:
        loop = MarketIntelligenceLoop(execute_action=self.execute_action)
        runtime_support = build_market_intelligence_runtime_support(
            runtime_infra=self.runtime_infra,
            recovery_support=self.recovery_support,
            outbox=self.outbox,
            distributed_lock=self.distributed_lock,
        )
        scheduler = MarketIntelligenceSchedulerService(
            loop=loop,
            orchestration=self.orchestration,
            distributed_lock=runtime_support.distributed_lock,
            scheduler_leader_election=runtime_support.scheduler_leader_election,
        )
        supervisor = MarketIntelligenceSchedulerSupervisor(scheduler=scheduler, tenant_id="tenant-default", observability=self.runtime_observability)
        runtime = MarketIntelligenceRuntime(loop=loop, scheduler=scheduler, supervisor=supervisor)
        if self.runtime_registry is not None:
            runtime.attachment_report = attach_market_intelligence_runtime_to_registry(
                registry=self.runtime_registry,
                runtime=runtime,
                observability=self.runtime_observability,
            )
        plane = self.managed_runtime_plane
        if plane is None and self.runtime_registry is not None and hasattr(self.runtime_registry, 'has') and hasattr(self.runtime_registry, 'get'):
            if self.runtime_registry.has(RuntimeServiceName.MANAGED_RUNTIME_PLANE):
                candidate = self.runtime_registry.get(RuntimeServiceName.MANAGED_RUNTIME_PLANE)
                if isinstance(candidate, ManagedRuntimePlane):
                    plane = candidate
        if plane is not None:
            plane.register_runtime(
                name=RuntimeServiceName.MARKET_INTELLIGENCE_RUNTIME,
                runtime=runtime,
                owner_service=RuntimeServiceName.MARKET_WATCH,
                dependencies=(),
            )
        return runtime


def build_market_intelligence_runtime(*, execute_action: Callable[[str, Mapping[str, Any]], Mapping[str, Any]], schedules: Mapping[str, SyncSchedule] | None = None, distributed_lock: DistributedLock | None = None, distributed_lock_backend_name: str | None = None, runtime_infra: Any | None = None, recovery_support: RuntimeExecutorRecoverySupport | None = None, outbox: Any | None = None, runtime_registry: Any | None = None, runtime_observability: RuntimeObservability | None = None, managed_runtime_plane: ManagedRuntimePlane | None = None) -> MarketIntelligenceRuntime:
    orchestration = MarketIntelligenceOrchestration()
    for name, schedule in dict(schedules or {}).items():
        orchestration.register(str(name), schedule)
    lock = distributed_lock if distributed_lock is not None else build_distributed_lock(backend_name=distributed_lock_backend_name or 'memory')
    return MarketIntelligenceBoot(
        execute_action=execute_action,
        orchestration=orchestration,
        distributed_lock=lock,
        runtime_infra=runtime_infra,
        recovery_support=recovery_support,
        outbox=outbox,
        runtime_registry=runtime_registry,
        runtime_observability=runtime_observability,
        managed_runtime_plane=managed_runtime_plane,
    ).build()
